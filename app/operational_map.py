from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, QStandardPaths
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from .offline_maps import TileCache
from .map_cache_server import LocalTileServer

BASE = Path(__file__).resolve().parent.parent


class OperationalMap(QWidget):
    """QGroundControl-style operational map for the CCM application.

    This intentionally does not use Qt Location's generic OSM provider. The
    map is rendered by Leaflet in an isolated QWebEngineView so Street,
    Satellite and Hybrid layers are explicit, predictable and independent of
    the QGroundControl installation.

    Telemetry remains the source of truth for all camera/target positions.
    """

    map_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 360)
        self._map_mode = "Street"
        self._selected_id = None
        self._state = {"cameras": [], "targets": [], "links": []}
        self._ready = False
        self._pending_mode = None
        self._pending_center = None
        self._view_initialized = False

        cache_base = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)) / "map_cache"
        self.tile_cache = TileCache(cache_base)
        self.tile_server = LocalTileServer(cache_base)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.view)

        html = BASE / "web" / "map.html"
        self.view.setUrl(QUrl.fromLocalFile(str(html)))

    def _on_load_finished(self, ok):
        self._ready = bool(ok)
        if not ok:
            self.map_error.emit("Operational map HTML failed to load")
            return
        self._apply_state()
        self.view.page().runJavaScript(
            f"window.ccmMap && window.ccmMap.setTileServer({json.dumps(self.tile_server.base_url)});"
        )
        self.set_map_mode(self._map_mode)
        if self._pending_center:
            self._center_on(*self._pending_center)
            self._pending_center = None
        self._view_initialized = False

    @staticmethod
    def _destination(lat, lon, bearing_deg, distance_m):
        r = 6371008.8
        b = math.radians(bearing_deg)
        d = distance_m / r
        p = math.radians(lat)
        l = math.radians(lon)
        p2 = math.asin(
            math.sin(p) * math.cos(d)
            + math.cos(p) * math.sin(d) * math.cos(b)
        )
        l2 = l + math.atan2(
            math.sin(b) * math.sin(d) * math.cos(p),
            math.cos(d) - math.sin(p) * math.sin(p2),
        )
        return math.degrees(p2), ((math.degrees(l2) + 540) % 360) - 180

    def set_state(self, cameras, targets):
        cameras = cameras or {}
        targets = targets or {}
        cams, tgts, links = [], [], []

        for cid, c in cameras.items():
            lat, lon = float(c.lat), float(c.lon)
            color = getattr(c, "color", "#22c55e")
            heading = float(getattr(c, "heading_deg", 0.0))
            fov = float(getattr(c, "fov_deg", 60.0))
            cams.append({
                "id": str(cid),
                "name": getattr(c, "name", cid),
                "lat": lat, "lon": lon,
                "heading": heading,
                "fov": fov,
                "altitude": float(getattr(c, "altitude_m", 0.0)),
                "azimuth": getattr(c, "azimuth_deg", getattr(c, "bearing_deg", None)),
                "elevation": getattr(c, "elevation_deg", None),
                "range": getattr(c, "range_m", None),
                "color": color,
                "status": getattr(c, "status", "UNKNOWN"),
                "alarm": getattr(c, "alarm_category", "NONE"),
            })
            tid = getattr(c, "target_id", None)
            if tid and tid in targets:
                t = targets[tid]
                links.append({
                    "camera_id": str(cid), "target_id": str(tid),
                    "color": color,
                })

        for tid, t in targets.items():
            tgts.append({
                "id": str(tid),
                "lat": float(t.lat), "lon": float(t.lon),
                "altitude": float(getattr(t, "altitude_m", 0.0)),
                "color": getattr(t, "color", "#facc15"),
                "category": getattr(t, "category", "NONE"),
                "confidence": float(getattr(t, "confidence", 0.0)),
            })

        self._state = {"cameras": cams, "targets": tgts, "links": links}
        self._apply_state()

        # Only establish the initial view once. Telemetry can arrive continuously,
        # but it must NOT recenter the map on every packet; otherwise the operator
        # cannot pan to another location or zoom out.
        if cams and not self._view_initialized:
            c = cams[0]
            self._center_on(c["lat"], c["lon"], 14)
            self._view_initialized = True

    def _apply_state(self):
        if not self._ready:
            return
        payload = json.dumps(self._state, separators=(",", ":"))
        script = f"window.ccmMap && window.ccmMap.update({payload});"
        self.view.page().runJavaScript(script)

    def set_map_mode(self, mode):
        mode = str(mode)
        if mode not in ("Street", "Satellite", "Hybrid"):
            mode = "Street"
        self._map_mode = mode
        if not self._ready:
            self._pending_mode = mode
            return
        self.view.page().runJavaScript(
            f"window.ccmMap && window.ccmMap.setMode({json.dumps(mode)});"
        )

    def select_camera(self, cid, center=True):
        """Select a camera. Centering is only done for an explicit operator action."""
        self._selected_id = cid
        if self._ready:
            if center:
                self.view.page().runJavaScript(
                    f"window.ccmMap && window.ccmMap.selectCamera({json.dumps(str(cid))});"
                )
            else:
                self.view.page().runJavaScript(
                    f"window.ccmMap && window.ccmMap.setSelected({json.dumps(str(cid))});"
                )
        if center:
            self.update_center_from_state()

    def update_center_from_state(self):
        for c in self._state.get("cameras", []):
            if c["id"] == self._selected_id:
                self._center_on(c["lat"], c["lon"], 15)
                return

    def _center_on(self, lat, lon, zoom=15):
        self._pending_center = (float(lat), float(lon), float(zoom))
        if not self._ready:
            return
        self._pending_center = None
        self.view.page().runJavaScript(
            f"window.ccmMap && window.ccmMap.centerOn({float(lat)},{float(lon)},{float(zoom)});"
        )

    def recenter(self):
        self.update_center_from_state()

    def refresh_local_tiles(self):
        if self._ready:
            self.view.page().runJavaScript(
                f"window.ccmMap && window.ccmMap.setTileServer({json.dumps(self.tile_server.base_url)});"
            )

    def fit_all(self):
        if self._ready:
            self.view.page().runJavaScript("window.ccmMap && window.ccmMap.fitAll();")

    def current_center(self):
        if self._state.get("cameras"):
            c = next((x for x in self._state["cameras"] if x["id"] == self._selected_id), self._state["cameras"][0])
            return float(c["lat"]), float(c["lon"])
        return 0.0, 0.0

    def close(self):
        self.tile_server.close()
