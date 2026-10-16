from __future__ import annotations

import math
import os
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot


class TileCache:
    """Simple persistent XYZ tile cache used by the CCM map engine."""
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.providers = {
            "Street": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "Labels": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        }

    @staticmethod
    def _substitute(template, z, x, y):
        return template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)).replace("{s}", "a")

    def path(self, provider: str, z: int, x: int, y: int) -> Path:
        return self.root / provider.lower() / str(z) / str(x) / f"{y}.png"

    def has(self, provider: str, z: int, x: int, y: int) -> bool:
        return self.path(provider, z, x, y).is_file()

    def count(self, provider=None) -> int:
        base = self.root / provider.lower() if provider else self.root
        if not base.exists():
            return 0
        return sum(1 for p in base.rglob("*.png"))

    def tile_count(self, lat1, lon1, lat2, lon2, zmin, zmax):
        total = 0
        for z in range(zmin, zmax + 1):
            x1, y1 = self.latlon_to_tile(lat1, lon1, z)
            x2, y2 = self.latlon_to_tile(lat2, lon2, z)
            total += (abs(x2 - x1) + 1) * (abs(y2 - y1) + 1)
        return total

    @staticmethod
    def latlon_to_tile(lat, lon, z):
        n = 2 ** z
        lat = max(-85.05112878, min(85.05112878, float(lat)))
        x = int((float(lon) + 180.0) / 360.0 * n)
        r = math.radians(lat)
        y = int((1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * n)
        return max(0, min(n - 1, x)), max(0, min(n - 1, y))


class TileDownloadWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, cache: TileCache, provider: str, bounds, zmin: int, zmax: int):
        super().__init__()
        self.cache = cache
        self.provider = provider
        self.bounds = bounds
        self.zmin = zmin
        self.zmax = zmax
        self.cancelled = False

    @Slot()
    def run(self):
        lat1, lon1, lat2, lon2 = self.bounds
        total = self.cache.tile_count(lat1, lon1, lat2, lon2, self.zmin, self.zmax)
        done = 0
        ok = 0
        try:
            for z in range(self.zmin, self.zmax + 1):
                x1, y1 = self.cache.latlon_to_tile(lat1, lon1, z)
                x2, y2 = self.cache.latlon_to_tile(lat2, lon2, z)
                xa, xb = sorted((x1, x2))
                ya, yb = sorted((y1, y2))
                n = 2 ** z
                for x in range(xa, xb + 1):
                    for y in range(ya, yb + 1):
                        if self.cancelled:
                            self.finished.emit(done, ok)
                            return
                        p = self.cache.path(self.provider, z, x, y)
                        done += 1
                        if p.exists():
                            ok += 1
                            self.progress.emit(done, total, f"Cached z{z}/{x}/{y}")
                            continue
                        p.parent.mkdir(parents=True, exist_ok=True)
                        url = self.cache._substitute(self.cache.providers[self.provider], z, x, y)
                        try:
                            req = urllib.request.Request(url, headers={"User-Agent": "CentralCameraMonitor/8.0"})
                            with urllib.request.urlopen(req, timeout=12) as r:
                                data = r.read()
                            if data:
                                tmp = p.with_suffix(".tmp")
                                tmp.write_bytes(data)
                                os.replace(tmp, p)
                                ok += 1
                        except Exception:
                            pass
                        self.progress.emit(done, total, f"Downloading z{z}/{x}/{y}")
            self.finished.emit(done, ok)
        except Exception as exc:
            self.error.emit(str(exc))
            self.finished.emit(done, ok)
