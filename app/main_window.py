from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QSizePolicy, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QVBoxLayout, QWidget, QProgressBar, QSpinBox, QDoubleSpinBox, QFormLayout, QMessageBox, QRadioButton
)

from .simulation import SimulationManager
from .video import VideoSource
from .operational_map import OperationalMap
from .telemetry_receiver import TelemetryReceiver
from .offline_maps import TileDownloadWorker

BASE = Path(__file__).resolve().parent.parent

STYLE = """
*{font-family:'Segoe UI';}
QMainWindow,QWidget{background:#0b1118;color:#dbe7f3;}
QFrame#panel,QFrame#videoCard,QFrame#statusCard,QFrame#logCard,QFrame#mapCard,QFrame#controlsCard{background:#101923;border:1px solid #263445;border-radius:9px;}
QLabel#appTitle{font-size:18px;font-weight:700;color:#f8fafc;}
QLabel#section{font-size:14px;font-weight:700;color:#f8fafc;}
QLabel#pageTitle{font-size:17px;font-weight:700;color:#f8fafc;}
QLabel#muted{color:#8392a6;}
QLabel#green{color:#35d07f;font-weight:700;}
QLabel#warning{color:#f4b942;font-weight:700;}
QLabel#alarm{font-size:12px;font-weight:700;padding:5px 8px;border-radius:4px;}
QPushButton#nav{background:transparent;border:none;border-radius:5px;padding:10px 15px;color:#aebdce;font-size:13px;}
QPushButton#nav:hover{background:#162333;color:#f8fafc;}
QPushButton#nav:checked{background:#1478e8;color:white;}
QPushButton#primary{background:#1478e8;color:white;border:1px solid #2187f2;border-radius:6px;padding:9px 14px;font-weight:600;}
QPushButton#secondary{background:#1a2634;color:#c9d5e3;border:1px solid #344356;border-radius:6px;padding:8px 12px;}
QPushButton#danger{background:#7f1d1d;color:#fecaca;border:1px solid #991b1b;border-radius:6px;padding:8px 12px;font-weight:600;}
QLineEdit,QComboBox{background:#0d151f;border:1px solid #304052;border-radius:5px;padding:7px;color:#e5edf5;}
QListWidget{background:#0e1721;border:none;}
QListWidget::item{padding:10px 8px;border-bottom:1px solid #1d2a38;}
QListWidget::item:selected{background:#125da8;border-radius:5px;}
QTableWidget{background:#0e1721;border:1px solid #263445;gridline-color:#1d2a38;alternate-background-color:#111c28;}
QHeaderView::section{background:#162333;color:#aebdce;padding:8px;border:0;border-right:1px solid #263445;font-weight:600;}
QTableWidget::item{padding:7px;}
QSplitter::handle{background:#1d2936;}
"""

ALARM_META = {
    "NONE": {"label": "NO ALARM", "bg": "#273444", "fg": "#b9c6d4"},
    "FRIENDLY": {"label": "FRIENDLY", "bg": "#14532d", "fg": "#86efac"},
    "SUSPICIOUS": {"label": "SUSPICIOUS", "bg": "#7f1d1d", "fg": "#fecaca"},
}


def card(title=None):
    f = QFrame(); f.setObjectName("panel")
    l = QVBoxLayout(f); l.setContentsMargins(12, 10, 12, 10); l.setSpacing(7)
    if title:
        x = QLabel(title); x.setObjectName("section"); l.addWidget(x)
    return f, l


class ClickableImage(QLabel):
    clicked = Signal()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class VideoPreviewWindow(QDialog):
    def __init__(self, camera, parent=None):
        super().__init__(parent)
        self.camera_id = camera.id
        self.setWindowTitle(f"Camera Preview - {camera.id} - {camera.name}")
        self.resize(1100, 700); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel(f"{camera.id}  |  {camera.name}"); title.setObjectName("section"); top.addWidget(title); top.addStretch()
        self.status = QLabel("LIVE"); self.status.setStyleSheet("background:#14532d;color:#86efac;padding:4px 8px;border-radius:4px;font-weight:700"); top.addWidget(self.status)
        layout.addLayout(top)
        self.image = ClickableImage("Waiting for video..."); self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet("background:#070c11;border-radius:5px;color:#708196")
        self.image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); layout.addWidget(self.image, 1)
        self.info = QLabel("Expanded live preview"); self.info.setObjectName("muted"); layout.addWidget(self.info)

    def set_frame(self, img):
        self.image.setPixmap(QPixmap.fromImage(img).scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class VideoCard(QFrame):
    clicked = Signal(str)
    def __init__(self, c, parent=None):
        super().__init__(parent); self.camera = c; self.setObjectName("videoCard"); self.setCursor(Qt.PointingHandCursor)
        l = QVBoxLayout(self); l.setContentsMargins(8, 7, 8, 7); l.setSpacing(5)
        top = QHBoxLayout(); d = QLabel("●"); d.setStyleSheet(f"color:{c.color};font-size:13px"); top.addWidget(d)
        t = QLabel(f"{c.id}  -  {c.name}"); t.setStyleSheet("font-weight:600;color:#f4f7fa"); top.addWidget(t); top.addStretch()
        self.alarm = QLabel("NO ALARM"); self.alarm.setObjectName("alarm"); top.addWidget(self.alarm)
        self.live = QLabel("LIVE"); self.live.setStyleSheet("background:#e51f32;color:white;padding:2px 6px;border-radius:3px;font-weight:700"); top.addWidget(self.live); l.addLayout(top)
        self.image = ClickableImage("Waiting for video..."); self.image.setAlignment(Qt.AlignCenter); self.image.setMinimumHeight(100)
        self.image.clicked.connect(lambda: self.clicked.emit(self.camera.id)); self.image.setStyleSheet("background:#070c11;border-radius:5px;color:#708196")
        self.image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); l.addWidget(self.image, 1)
        b = QHBoxLayout(); self.meta = QLabel("SOURCE: FILE"); self.meta.setObjectName("muted"); b.addWidget(self.meta); b.addStretch()
        self.hint = QLabel("Click to expand"); self.hint.setObjectName("muted"); b.addWidget(self.hint); l.addLayout(b)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.clicked.emit(self.camera.id)
        super().mousePressEvent(event)

    def set_frame(self, img):
        self.image.setPixmap(QPixmap.fromImage(img).scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_source(self, s): self.meta.setText("SOURCE: " + s)

    def set_alarm(self, category):
        m = ALARM_META.get(category, ALARM_META["NONE"])
        self.alarm.setText(m["label"])
        self.alarm.setStyleSheet(f"background:{m['bg']};color:{m['fg']};padding:5px 8px;border-radius:4px;font-weight:700")


class OfflineMapDialog(QDialog):
    """Operator dialog for downloading a bounded local map tile set."""
    def __init__(self, operational_map, parent=None):
        super().__init__(parent)
        self.omap = operational_map
        self.setWindowTitle("Offline Map Manager")
        self.resize(520, 430)
        self.setStyleSheet(STYLE)
        self._thread = None
        self._worker = None
        self._stage = []
        self._stage_index = 0

        root = QVBoxLayout(self)
        title = QLabel("Offline Map Manager"); title.setObjectName("pageTitle"); root.addWidget(title)
        root.addWidget(QLabel("Download a bounded map area for use when the Internet is unavailable. Provider terms must permit offline storage."))

        form = QFormLayout(); form.setSpacing(8)
        self.provider = QComboBox(); self.provider.addItems(["Street", "Satellite", "Hybrid"]); form.addRow("Map type", self.provider)
        self.lat = QDoubleSpinBox(); self.lat.setRange(-85.0,85.0); self.lat.setDecimals(6); self.lat.setSingleStep(0.001)
        self.lon = QDoubleSpinBox(); self.lon.setRange(-180.0,180.0); self.lon.setDecimals(6); self.lon.setSingleStep(0.001)
        self.radius = QDoubleSpinBox(); self.radius.setRange(0.1,100.0); self.radius.setDecimals(1); self.radius.setValue(5.0); self.radius.setSuffix(" km")
        self.zmin = QSpinBox(); self.zmin.setRange(2,19); self.zmin.setValue(10)
        self.zmax = QSpinBox(); self.zmax.setRange(2,19); self.zmax.setValue(15)
        form.addRow("Center latitude", self.lat); form.addRow("Center longitude", self.lon); form.addRow("Radius", self.radius)
        form.addRow("Minimum zoom", self.zmin); form.addRow("Maximum zoom", self.zmax)
        root.addLayout(form)
        self.estimate = QLabel("Estimated tiles: --"); self.estimate.setObjectName("muted"); root.addWidget(self.estimate)
        self.provider.currentTextChanged.connect(self._estimate)
        for x in (self.lat,self.lon,self.radius,self.zmin,self.zmax): x.valueChanged.connect(self._estimate)

        row=QHBoxLayout(); use=QPushButton("Use Selected Camera"); use.setObjectName("secondary"); use.clicked.connect(self._use_selected); row.addWidget(use)
        self.start=QPushButton("Download Map Area"); self.start.setObjectName("primary"); self.start.clicked.connect(self._start); row.addWidget(self.start)
        self.cancel=QPushButton("Cancel"); self.cancel.setObjectName("secondary"); self.cancel.clicked.connect(self._cancel); row.addWidget(self.cancel)
        root.addLayout(row)
        self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); root.addWidget(self.progress)
        self.status=QLabel("Ready"); self.status.setObjectName("muted"); root.addWidget(self.status)
        self._use_selected(); self._estimate()

    def _use_selected(self):
        lat,lon=self.omap.current_center(); self.lat.setValue(lat); self.lon.setValue(lon)

    def _bounds(self):
        r=float(self.radius.value())
        dlat=r/111.32
        dlon=r/(111.32*max(0.15,abs(__import__('math').cos(__import__('math').radians(self.lat.value())))))
        return (self.lat.value()-dlat,self.lon.value()-dlon,self.lat.value()+dlat,self.lon.value()+dlon)

    def _estimate(self):
        if self.zmax.value()<self.zmin.value(): self.zmax.setValue(self.zmin.value())
        b=self._bounds(); n=self.omap.tile_cache.tile_count(*b,self.zmin.value(),self.zmax.value())
        if self.provider.currentText()=="Hybrid": n*=2
        self.estimate.setText(f"Estimated tiles: {n:,}  |  Existing cached tiles are skipped")
        if n>5000: self.estimate.setStyleSheet("color:#f4b942;font-weight:700")
        else: self.estimate.setStyleSheet("")

    def _start(self):
        if self.zmax.value()<self.zmin.value():
            QMessageBox.warning(self,"Invalid zoom range","Maximum zoom must be greater than or equal to minimum zoom."); return
        self._stage = ["Satellite","Labels"] if self.provider.currentText()=="Hybrid" else [self.provider.currentText()]
        self._stage_index=0; self.start.setEnabled(False); self.provider.setEnabled(False); self._run_stage()

    def _run_stage(self):
        provider=self._stage[self._stage_index]
        self.status.setText(f"Downloading {provider} tiles…")
        self.progress.setValue(0)
        self._thread=QThread(self); self._worker=TileDownloadWorker(self.omap.tile_cache,provider,self._bounds(),self.zmin.value(),self.zmax.value())
        self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._progress); self._worker.finished.connect(self._finished_stage); self._worker.error.connect(lambda e:self.status.setText("Download warning: "+e))
        self._thread.start()

    def _progress(self,done,total,msg):
        self.progress.setValue(int(done*100/max(1,total))); self.status.setText(msg)

    def _finished_stage(self,done,ok):
        if self._thread:
            self._thread.quit(); self._thread.wait(2000); self._thread=None
        self._stage_index+=1
        if self._stage_index < len(self._stage): self._run_stage(); return
        self.status.setText(f"Offline map ready: {ok} tiles downloaded/cached.")
        self.progress.setValue(100); self.start.setEnabled(True); self.provider.setEnabled(True)
        self.omap.refresh_local_tiles()

    def _cancel(self):
        if self._worker: self._worker.cancelled=True
        if self._thread: self._thread.quit()
        self.reject()


class EngagementDialog(QDialog):
    """Non-commanding tasking dialog: prepares a training/coordination request only."""
    def __init__(self, checkpost, camera, available, parent=None):
        super().__init__(parent)
        self.checkpost = checkpost
        self.camera = camera
        self.available = available
        self.result_data = None
        self.setWindowTitle(f"Engage — {checkpost}")
        self.resize(540, 500)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel(f"Tasking Request  |  {checkpost}"); title.setObjectName("pageTitle"); root.addWidget(title)
        note = QLabel("Training / coordination interface only — no flight, weapon, or external command is issued by this dialog.")
        note.setWordWrap(True); note.setObjectName("muted"); root.addWidget(note)
        availability = QLabel(f"UAV available at {checkpost}: {available}"); availability.setObjectName("green"); root.addWidget(availability)

        source = QFrame(); source.setObjectName("panel"); sl = QVBoxLayout(source)
        sl.addWidget(self._section_label("Target Source"))
        self.camera_target = QRadioButton("Use camera-reported target")
        self.manual_target = QRadioButton("Enter target coordinates manually")
        self.camera_target.setChecked(True)
        sl.addWidget(self.camera_target); sl.addWidget(self.manual_target)
        root.addWidget(source)

        self.target_box = QFrame(); self.target_box.setObjectName("panel"); tl = QVBoxLayout(self.target_box)
        tl.addWidget(self._section_label("Target Data"))
        self.target_info = QLabel(); self.target_info.setWordWrap(True); tl.addWidget(self.target_info)
        root.addWidget(self.target_box)

        form_frame = QFrame(); form_frame.setObjectName("panel"); fl = QFormLayout(form_frame)
        self.lat = QDoubleSpinBox(); self.lat.setRange(-90,90); self.lat.setDecimals(6); self.lat.setSingleStep(0.000001)
        self.lon = QDoubleSpinBox(); self.lon.setRange(-180,180); self.lon.setDecimals(6); self.lon.setSingleStep(0.000001)
        self.alt = QDoubleSpinBox(); self.alt.setRange(-1000,20000); self.alt.setDecimals(1); self.alt.setSuffix(" m")
        fl.addRow("Latitude", self.lat); fl.addRow("Longitude", self.lon); fl.addRow("Altitude", self.alt)
        root.addWidget(form_frame)

        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject); buttons.addWidget(cancel)
        proceed = QPushButton("Proceed to Engage"); proceed.setObjectName("primary"); proceed.clicked.connect(self._confirm); buttons.addWidget(proceed)
        root.addLayout(buttons)
        self.camera_target.toggled.connect(self._source_changed)
        self._load_camera_target()
        self._source_changed(True)

    @staticmethod
    def _section_label(text):
        x = QLabel(text); x.setObjectName("section"); return x

    def _load_camera_target(self):
        c = self.camera
        if c and c.target_id and c.target_lat is not None and c.target_lon is not None:
            self.target_info.setText(
                f"Target: {c.target_id}\n"
                f"Latitude: {c.target_lat:.6f}°\n"
                f"Longitude: {c.target_lon:.6f}°\n"
                f"Altitude: {c.target_altitude_m if c.target_altitude_m is not None else 0:.1f} m\n"
                f"Classification: {c.alarm_category}\n"
                f"Confidence: {c.alarm_confidence*100:.1f}%\n"
                f"Range: {c.range_m:.1f} m" if c.range_m is not None else
                f"Target: {c.target_id}\nLatitude: {c.target_lat:.6f}°\nLongitude: {c.target_lon:.6f}°\n"
                f"Altitude: {c.target_altitude_m if c.target_altitude_m is not None else 0:.1f} m\n"
                f"Classification: {c.alarm_category}\nConfidence: {c.alarm_confidence*100:.1f}%\nRange: —"
            )
            self.lat.setValue(float(c.target_lat)); self.lon.setValue(float(c.target_lon)); self.alt.setValue(float(c.target_altitude_m or 0))
        else:
            self.target_info.setText("No camera target data is currently available.")

    def _source_changed(self, camera_mode):
        self.lat.setEnabled(not camera_mode); self.lon.setEnabled(not camera_mode); self.alt.setEnabled(not camera_mode)
        if camera_mode: self._load_camera_target()
        self.target_box.setEnabled(True)

    def _confirm(self):
        if self.camera_target.isChecked():
            if not (self.camera and self.camera.target_id and self.camera.target_lat is not None and self.camera.target_lon is not None):
                QMessageBox.warning(self, "Target Data Unavailable", "The selected checkpost has no valid camera target coordinates.")
                return
            target = {
                "source": "CAMERA",
                "id": self.camera.target_id,
                "lat": float(self.camera.target_lat),
                "lon": float(self.camera.target_lon),
                "alt": float(self.camera.target_altitude_m or 0),
                "category": self.camera.alarm_category,
                "confidence": float(self.camera.alarm_confidence),
            }
        else:
            target = {
                "source": "MANUAL",
                "id": "MANUAL",
                "lat": float(self.lat.value()),
                "lon": float(self.lon.value()),
                "alt": float(self.alt.value()),
                "category": "UNCLASSIFIED",
                "confidence": 0.0,
            }
        msg = QMessageBox(self); msg.setIcon(QMessageBox.Warning); msg.setWindowTitle("Confirm Engagement")
        msg.setText(f"Do you want to engage one UAV from {self.checkpost}?")
        msg.setInformativeText(
            f"Target source: {target['source']}\n"
            f"Coordinates: {target['lat']:.6f}, {target['lon']:.6f}\n"
            f"Altitude: {target['alt']:.1f} m\n\n"
            "This is a training/coordination action. No external UAV command will be transmitted."
        )
        yes = msg.addButton("Confirm Engage", QMessageBox.AcceptRole); msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() is yes:
            self.result_data = target
            self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Central Camera Monitor")
        self.resize(1600, 950); self.setMinimumSize(1200, 760); self.setStyleSheet(STYLE)
        self.sim = SimulationManager(str(BASE / "config" / "scenario.yaml")); self.selected_id = self.sim.selected_camera
        self.video_sources = {}; self.video_cards = {}; self.camera_page_cards = {}; self.preview_windows = {}
        self._last_alarm_state = {}; self.alarm_history = []
        self.assets = {a.get("checkpost_id", a.get("name", "CHECKPOST")): dict(a) for a in self.sim.cfg.get("assets", [])}
        self.asset_cards = {}
        self._build_ui(); self._populate_cameras()
        self.sim.updated.connect(self.on_update)
        self.telemetry = TelemetryReceiver("0.0.0.0", 5010); self.telemetry.packet_received.connect(self.on_packet); self.telemetry.start()
        self.sim.start()
        self.clock_timer = QTimer(self); self.clock_timer.timeout.connect(self._tick); self.clock_timer.start(1000)
        self._log("INFO", "System started"); self._log("INFO", "QGC-style map engine initialized (independent of QGroundControl)"); self._log("INFO", "Telemetry receiver listening UDP :5010")

    def _label(self, text, obj=None):
        x = QLabel(text)
        if obj: x.setObjectName(obj)
        return x

    def _build_header(self, outer):
        h = QHBoxLayout(); h.setSpacing(3)
        title = self._label("▣  Central Camera Monitor", "appTitle"); h.addWidget(title); h.addSpacing(10)
        self.nav_buttons = []
        names = [("▣ Monitor", 0), ("◈ Map", 1), ("▣ Cameras", 2), ("◉ Assets", 3), ("⚠ Alarms & Logs", 4), ("⚙ Settings", 5)]
        for n, idx in names:
            b = QPushButton(n); b.setObjectName("nav"); b.setCheckable(True); b.clicked.connect(lambda checked=False, i=idx: self._show_page(i)); self.nav_buttons.append(b); h.addWidget(b)
        self.nav_buttons[0].setChecked(True)
        h.addStretch(); self.global_alarm = self._label("● NO ACTIVE ALARMS", "green"); h.addWidget(self.global_alarm); h.addSpacing(12)
        self.connection = self._label("● Telemetry Listening", "green"); h.addWidget(self.connection); self.clock = self._label("", "muted"); h.addWidget(self.clock); outer.addLayout(h)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root); outer.setContentsMargins(10, 8, 10, 8); outer.setSpacing(7)
        self._build_header(outer)
        self.pages = QStackedWidget(); outer.addWidget(self.pages, 1)
        self.pages.addWidget(self._build_monitor_page())
        self.pages.addWidget(self._build_map_page())
        self.pages.addWidget(self._build_cameras_page())
        self.pages.addWidget(self._build_assets_page())
        self.pages.addWidget(self._build_alarm_page())
        self.pages.addWidget(self._build_settings_page())
        self._build_video_sources()

    def _build_monitor_page(self):
        body = QSplitter(Qt.Horizontal); body.setChildrenCollapsible(False)
        left = QFrame(); left.setObjectName("panel"); ll = QVBoxLayout(left); ll.setContentsMargins(10,10,10,10)
        head = QHBoxLayout(); head.addWidget(self._label("Cameras (4)", "section")); head.addStretch(); ll.addLayout(head)
        self.camera_list = QListWidget(); self.camera_list.currentRowChanged.connect(self.select_row); ll.addWidget(self.camera_list, 1)
        ctl, cl = card("Video Source"); self.source_type = QComboBox(); self.source_type.addItems(["FILE / REPLAY", "RTSP STREAM", "USB CAMERA", "BUILT-IN CAMERA"]); cl.addWidget(self._label("Source Type")); cl.addWidget(self.source_type)
        self.source_value = QLineEdit(); self.source_value.setPlaceholderText("RTSP URL or camera index"); cl.addWidget(self._label("Source / Device")); cl.addWidget(self.source_value)
        row = QHBoxLayout(); self.connect_btn = QPushButton("Connect"); self.connect_btn.setObjectName("primary"); self.connect_btn.clicked.connect(self.connect_selected_source); row.addWidget(self.connect_btn)
        self.disconnect_btn = QPushButton("Disconnect"); self.disconnect_btn.setObjectName("secondary"); self.disconnect_btn.clicked.connect(self.disconnect_selected_source); row.addWidget(self.disconnect_btn); cl.addLayout(row)
        self.source_hint = self._label("FILE: local replay source", "muted"); cl.addWidget(self.source_hint); ll.addWidget(ctl)
        tel, tl = card("Telemetry"); self.telemetry_mode = QLabel("TEST / REPLAY DATA"); self.telemetry_mode.setObjectName("green"); tl.addWidget(self.telemetry_mode)
        self.tel_info = self._label("UDP :5010  |  CCM-TELEMETRY v1.0", "muted"); tl.addWidget(self.tel_info); self.alarm_info = self._label("Alarm: NONE", "muted"); tl.addWidget(self.alarm_info); ll.addWidget(tel)
        body.addWidget(left)

        center = QSplitter(Qt.Vertical); center.setChildrenCollapsible(False)
        mc, ml = card(); toolbar = QHBoxLayout(); toolbar.addWidget(self._label("Operational Map", "section")); toolbar.addStretch(); toolbar.addWidget(self._label("Map", "muted")); self.monitor_map_mode = QComboBox(); self.monitor_map_mode.addItems(["Street", "Satellite", "Hybrid"]); self.monitor_map_mode.currentTextChanged.connect(self._map_mode_changed); toolbar.addWidget(self.monitor_map_mode); offline_m = QPushButton("Offline Maps"); offline_m.setObjectName("secondary"); offline_m.clicked.connect(lambda: self._open_offline_manager(self.monitor_map)); toolbar.addWidget(offline_m); ml.addLayout(toolbar)
        self.monitor_map = OperationalMap(); self.monitor_map.map_error.connect(lambda e: self._log("ERROR", "Map: " + e.replace("\n", " | "))); ml.addWidget(self.monitor_map); center.addWidget(mc)
        logs = QSplitter(Qt.Horizontal); logc, logl = card("Event Log"); self.log = QListWidget(); logl.addWidget(self.log); logs.addWidget(logc)
        st, sl = card("System Status"); self.system_state = self._label("● All Systems Operational", "green"); sl.addWidget(self.system_state); self.status_labels = {}
        for k, v in [("Active Cameras", "4 / 4"), ("Telemetry", "LISTENING"), ("Alarms", "0 ACTIVE"), ("CPU", "--"), ("Network", "UDP :5010"), ("Uptime", "00:00:00")]:
            r = QHBoxLayout(); a = self._label(k, "muted"); b = self._label(v); r.addWidget(a); r.addStretch(); r.addWidget(b); sl.addLayout(r); self.status_labels[k] = b
        logs.addWidget(st); logs.setSizes([720,360]); center.addWidget(logs); center.setSizes([700,190]); body.addWidget(center)

        right = QFrame(); right.setObjectName("panel"); rl = QVBoxLayout(right); rl.setContentsMargins(7,7,7,7); rl.setSpacing(5)
        cambar = QHBoxLayout(); cambar.addWidget(self._label("Camera Previews", "section")); cambar.addStretch(); self.toggle_camera_wall_btn = QPushButton("Minimize"); self.toggle_camera_wall_btn.setObjectName("secondary"); self.toggle_camera_wall_btn.clicked.connect(self._toggle_camera_wall); cambar.addWidget(self.toggle_camera_wall_btn); rl.addLayout(cambar)
        self.camera_wall = QWidget(); grid = QGridLayout(self.camera_wall); grid.setContentsMargins(0,0,0,0); grid.setSpacing(6)
        for idx, c in enumerate(self.sim.cameras.values()):
            vc = VideoCard(c); vc.clicked.connect(self.open_camera_preview); self.video_cards[c.id] = vc; grid.addWidget(vc, idx, 0)
        for idx in range(len(self.sim.cameras)): grid.setRowStretch(idx,1)
        rl.addWidget(self.camera_wall,1)
        right.setMinimumWidth(285); right.setMaximumWidth(360)
        body.addWidget(right); body.setSizes([300,1050,320])
        return body

    def _toggle_camera_wall(self):
        hidden = self.camera_wall.isVisible()
        self.camera_wall.setVisible(not hidden)
        self.toggle_camera_wall_btn.setText("Show Cameras" if hidden else "Minimize")
        self._log("INFO", "Camera preview wall minimized" if hidden else "Camera preview wall restored")

    def _open_offline_manager(self, operational_map):
        dlg = OfflineMapDialog(operational_map, self)
        dlg.exec()

    def _build_map_page(self):
        # The dedicated map is created lazily when the Map tab is first shown.
        # QWebEngineView can be initialized while hidden inside QStackedWidget;
        # doing so can leave the second map with a blank rendering surface.
        # Creating it after the page is visible avoids that lifecycle problem.
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0)
        toolbar = QFrame(); toolbar.setObjectName("panel"); tl = QHBoxLayout(toolbar); tl.setContentsMargins(12,8,12,8)
        tl.addWidget(self._label("Operational Map", "pageTitle")); tl.addSpacing(15); tl.addWidget(self._label("View", "muted")); self.map_page_mode = QComboBox(); self.map_page_mode.addItems(["Street", "Satellite", "Hybrid"]); self.map_page_mode.currentTextChanged.connect(self._map_mode_changed); tl.addWidget(self.map_page_mode)
        offline = QPushButton("Offline Maps"); offline.setObjectName("secondary"); offline.clicked.connect(lambda: self._open_offline_manager(self.map) if hasattr(self, "map") else None); tl.addWidget(offline)
        rec = QPushButton("Recenter Selected"); rec.setObjectName("secondary"); rec.clicked.connect(lambda: self.map.recenter() if hasattr(self, "map") else None); tl.addWidget(rec); tl.addStretch(); self.map_page_status = self._label("Location driven by telemetry", "muted"); tl.addWidget(self.map_page_status); l.addWidget(toolbar)
        self.map_page_card, self.map_page_layout = card(); self.map_page_placeholder = self._label("Map engine will initialize when this page is opened…", "muted"); self.map_page_placeholder.setAlignment(Qt.AlignCenter); self.map_page_layout.addWidget(self.map_page_placeholder); l.addWidget(self.map_page_card,1)
        return page

    def _ensure_map_page_map(self):
        if hasattr(self, "map"):
            return self.map
        self.map_page_placeholder.deleteLater()
        self.map = OperationalMap()
        self.map.map_error.connect(lambda e: self._log("ERROR", "Map: " + e.replace("\n", " | ")))
        self.map_page_layout.addWidget(self.map)
        # Apply the currently selected layer after the page is visible.
        self.map.set_map_mode(self.map_page_mode.currentText())
        if hasattr(self, "_last_cameras"):
            self.map.set_state(self._last_cameras, getattr(self, "_last_targets", {}))
        self.map.view.page().runJavaScript(
            "setTimeout(function(){ window.dispatchEvent(new Event('resize')); "
            "if(window.ccmMap){ window.ccmMap.invalidateSize && window.ccmMap.invalidateSize(); } }, 150);"
        )
        return self.map

    def _build_cameras_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0)
        top = QFrame(); top.setObjectName("panel"); tl = QHBoxLayout(top); tl.addWidget(self._label("Camera Operations", "pageTitle")); tl.addStretch(); tl.addWidget(self._label("Click any preview to open a dedicated window", "muted")); l.addWidget(top)
        body = QSplitter(Qt.Horizontal); body.setChildrenCollapsible(False)
        left, ll = card("Camera Selection"); self.camera_page_list = QListWidget(); self.camera_page_list.currentRowChanged.connect(self._camera_page_select); ll.addWidget(self.camera_page_list); body.addWidget(left)
        right = QWidget(); grid = QGridLayout(right); grid.setSpacing(9)
        for idx, c in enumerate(self.sim.cameras.values()):
            vc = VideoCard(c); vc.clicked.connect(self.open_camera_preview); self.camera_page_cards[c.id] = vc; grid.addWidget(vc, idx//2, idx%2)
        grid.setRowStretch(0,1); grid.setRowStretch(1,1); body.addWidget(right); body.setSizes([250,1100]); l.addWidget(body,1)
        return page

    def _build_assets_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0); l.setSpacing(8)
        top = QFrame(); top.setObjectName("panel"); tl = QHBoxLayout(top)
        tl.addWidget(self._label("Asset Status", "pageTitle")); tl.addStretch()
        tl.addWidget(self._label("UAV availability by checkpost", "muted")); l.addWidget(top)
        note = QLabel("Engagement requests shown here are coordination/training records only. This application does not transmit flight or weapon commands.")
        note.setObjectName("warning"); note.setWordWrap(True); l.addWidget(note)
        grid_host = QWidget(); grid = QGridLayout(grid_host); grid.setSpacing(10)
        assets = list(self.assets.items())
        for idx, (aid, a) in enumerate(assets):
            checkpost = str(a.get("name", aid)); camera_id = str(a.get("camera_id", ""));
            c = self.sim.cameras.get(camera_id)
            f = QFrame(); f.setObjectName("panel"); fl = QVBoxLayout(f); fl.setContentsMargins(14,12,14,12)
            header = QHBoxLayout(); title = QLabel(checkpost); title.setObjectName("section"); header.addWidget(title); header.addStretch()
            status = QLabel(str(a.get("status", "ONLINE"))); status.setObjectName("green"); header.addWidget(status); fl.addLayout(header)
            info = QHBoxLayout(); left = QVBoxLayout(); left.addWidget(self._label("UAV AVAILABLE", "muted")); count = QLabel(str(int(a.get("uav_available", 0)))); count.setObjectName("pageTitle"); count.setStyleSheet("font-size:28px;font-weight:800;color:#35d07f;"); left.addWidget(count); info.addLayout(left)
            right = QVBoxLayout(); right.addWidget(self._label(f"TOTAL: {int(a.get('uav_total', a.get('uav_available',0)))}", "muted")); assigned = QLabel(f"Assigned: {int(a.get('uav_total', a.get('uav_available',0))) - int(a.get('uav_available',0))}"); assigned.setObjectName("muted"); right.addWidget(assigned); info.addLayout(right); fl.addLayout(info)
            target = QLabel(); target.setWordWrap(True); target.setObjectName("muted"); fl.addWidget(target)
            btn = QPushButton("Engage"); btn.setObjectName("primary"); btn.clicked.connect(lambda checked=False, aid=aid: self._open_engagement(aid)); fl.addWidget(btn)
            self.asset_cards[aid] = {"frame":f,"count":count,"assigned":assigned,"target":target,"button":btn,"camera_id":camera_id}
            grid.addWidget(f, idx//2, idx%2)
        grid.setRowStretch(0,1); grid.setRowStretch(1,1)
        l.addWidget(grid_host,1)
        self._refresh_asset_cards()
        return page

    def _refresh_asset_cards(self):
        for aid, card_data in self.asset_cards.items():
            a = self.assets.get(aid, {}); cid = card_data["camera_id"]; c = self.sim.cameras.get(cid)
            available = int(a.get("uav_available", 0)); total = int(a.get("uav_total", available));
            card_data["count"].setText(str(available)); card_data["assigned"].setText(f"Assigned: {max(0,total-available)}")
            card_data["button"].setEnabled(available > 0)
            if c and c.target_id and c.target_lat is not None and c.target_lon is not None:
                card_data["target"].setText(f"Target: {c.target_id}  |  {c.target_lat:.6f}, {c.target_lon:.6f}\nAlt {c.target_altitude_m or 0:.1f} m  |  {c.alarm_category}  |  {c.alarm_confidence*100:.0f}%")
            else:
                card_data["target"].setText("Target: No camera target available")

    def _open_engagement(self, aid):
        a = self.assets.get(aid, {}); cid = a.get("camera_id"); c = self.sim.cameras.get(cid); available = int(a.get("uav_available", 0))
        if available <= 0:
            QMessageBox.information(self, "No UAV Available", f"No available UAV is currently listed at {a.get('name', aid)}.")
            return
        dlg = EngagementDialog(str(a.get("name", aid)), c, available, self)
        if dlg.exec() == QDialog.Accepted and dlg.result_data:
            a["uav_available"] = max(0, available - 1); self.assets[aid] = a
            t = dlg.result_data
            self._log("TASK", f"Engagement request staged at {a.get('name', aid)} | {t['source']} | {t['lat']:.6f},{t['lon']:.6f}")
            self._refresh_asset_cards()
            QMessageBox.information(self, "Request Staged", f"Training/coordination engagement request recorded for {a.get('name', aid)}.\n\nTarget: {t['lat']:.6f}, {t['lon']:.6f}\nUAV reserved: 1\n\nNo external command was transmitted.")

    def _build_alarm_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0)
        summary = QHBoxLayout()
        for title, attr in [("Active Alarms", "active_alarm_count"), ("Suspicious", "suspicious_count"), ("Friendly", "friendly_count")]:
            f, fl = card(title); val = self._label("0", "pageTitle"); setattr(self, attr, val); fl.addWidget(val); summary.addWidget(f)
        l.addLayout(summary)
        split = QSplitter(Qt.Vertical); split.setChildrenCollapsible(False)
        event_card, el = card("Alarm / Classification History"); self.alarm_table = QTableWidget(0, 7); self.alarm_table.setHorizontalHeaderLabels(["Time","Camera","Target","Category","Confidence","Message","State"]); self.alarm_table.setAlternatingRowColors(True); self.alarm_table.verticalHeader().setVisible(False); self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.alarm_table.horizontalHeader().setSectionResizeMode(5,QHeaderView.Stretch); el.addWidget(self.alarm_table); split.addWidget(event_card)
        log_card, ll = card("System Event Log"); self.alarm_log = QListWidget(); ll.addWidget(self.alarm_log); split.addWidget(log_card); split.setSizes([500,250]); l.addWidget(split,1)
        return page

    def _build_settings_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0)
        f, fl = card("System Configuration"); fl.addWidget(self._label("Telemetry Protocol", "section")); fl.addWidget(self._label("CCM-TELEMETRY v1.0  |  UDP 0.0.0.0:5010", "muted")); fl.addSpacing(8); fl.addWidget(self._label("Map Provider", "section")); fl.addWidget(self._label("QGC-style independent map engine with explicit Street, Satellite and Hybrid providers. Map rendering is isolated from the QGroundControl installation.", "muted")); fl.addSpacing(8); fl.addWidget(self._label("Architecture", "section")); fl.addWidget(self._label("Telemetry-driven location and classification; camera sources remain replaceable with RTSP, USB, built-in or local replay sources.", "muted")); fl.addStretch(); l.addWidget(f); return page

    def _build_video_sources(self):
        for cid in self.sim.cameras:
            s = VideoSource(BASE / "videos", cid); s.set_camera(cid); s.frame_ready.connect(lambda img, cid=cid: self.on_frame(cid,img)); s.status_changed.connect(lambda st, cid=cid: self._log("VIDEO",f"{cid}: {st}")); self.video_sources[cid] = s

    def _show_page(self, idx):
        self.pages.setCurrentIndex(idx)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i == idx)
        if idx == 0:
            self.monitor_map.recenter()
        elif idx == 1:
            m = self._ensure_map_page_map()
            m.recenter()
            m.view.page().runJavaScript(
                "setTimeout(function(){ window.dispatchEvent(new Event('resize')); "
                "if(window.ccmMap){ window.ccmMap.invalidateSize && window.ccmMap.invalidateSize(); } }, 100);"
            )

    def _map_mode_changed(self, mode):
        if hasattr(self, "monitor_map"):
            self.monitor_map.set_map_mode(mode)
        if hasattr(self, "map"):
            self.map.set_map_mode(mode)
        if hasattr(self, "map_page_status"):
                self.map_page_status.setText(f"{mode} map | location driven by telemetry")
        # Keep the other selector synchronized without causing a loop.
        for combo in [getattr(self,"monitor_map_mode",None), getattr(self,"map_page_mode",None)]:
            if combo and combo.currentText() != mode: combo.blockSignals(True); combo.setCurrentText(mode); combo.blockSignals(False)

    def _populate_cameras(self):
        for c in self.sim.cameras.values():
            it = QListWidgetItem(f"●  {c.id}  -  {c.name}\n    {c.status}  |  {c.target_id or 'TARGET'} | {c.alarm_category}"); it.setData(Qt.UserRole,c.id); self.camera_list.addItem(it)
            it2 = QListWidgetItem(f"●  {c.id}  -  {c.name}\n    {c.status} | {c.alarm_category}"); it2.setData(Qt.UserRole,c.id); self.camera_page_list.addItem(it2)
        self.camera_list.setCurrentRow(0); self.camera_page_list.setCurrentRow(0)

    def _camera_page_select(self,row):
        if row < 0: return
        cid = self.camera_page_list.item(row).data(Qt.UserRole); self.selected_id = cid; self.sim.set_selected_camera(cid); self.monitor_map.select_camera(cid);
        if hasattr(self, "map"): self.map.select_camera(cid)
        self._refresh_source_fields()

    def select_row(self,row):
        if row < 0: return
        cid = self.camera_list.item(row).data(Qt.UserRole); self.selected_id = cid; self.sim.set_selected_camera(cid);
        if hasattr(self, "map"): self.map.select_camera(cid)
        self._refresh_source_fields(); self._log("INFO",f"Selected {cid}")

    def _refresh_source_fields(self):
        cid=self.selected_id; s=self.video_sources[cid]
        self.source_type.setCurrentText({"FILE":"FILE / REPLAY","RTSP":"RTSP STREAM","USB":"USB CAMERA","BUILTIN":"BUILT-IN CAMERA"}.get(s.source_type,"FILE / REPLAY")); self.source_value.setText(s.source_value if s.source_type!="FILE" else f"videos/{cid}.mp4")
        self.source_hint.setText("RTSP supports rtsp://... | USB/Built-in use device index 0,1,2...")

    def connect_selected_source(self):
        cid=self.selected_id; typ=self.source_type.currentText(); val=self.source_value.text().strip(); mapping={"FILE / REPLAY":"FILE","RTSP STREAM":"RTSP","USB CAMERA":"USB","BUILT-IN CAMERA":"BUILTIN"}; typ=mapping[typ]
        if typ=="FILE": val=str(BASE/"videos"/f"{cid}.mp4")
        elif typ in ("USB","BUILTIN"): val=val or "0"
        elif typ=="RTSP" and not val: return
        self.video_sources[cid].configure(typ,val); self.video_cards[cid].set_source(typ); self.camera_page_cards[cid].set_source(typ); self._log("VIDEO",f"{cid} connected: {typ} {val}")

    def disconnect_selected_source(self):
        cid=self.selected_id; self.video_sources[cid].configure("FILE",str(BASE/"videos"/"__missing__.mp4")); self._log("VIDEO",f"{cid} disconnected")

    def open_camera_preview(self,cid):
        if cid not in self.preview_windows or not self.preview_windows[cid] or not self.preview_windows[cid].isVisible(): self.preview_windows[cid]=VideoPreviewWindow(self.sim.cameras[cid],self)
        self.preview_windows[cid].show(); self.preview_windows[cid].raise_(); self.preview_windows[cid].activateWindow(); self._log("VIDEO",f"Opened expanded preview for {cid}")

    def on_frame(self,cid,img):
        if cid in self.video_cards: self.video_cards[cid].set_frame(img)
        if cid in self.camera_page_cards: self.camera_page_cards[cid].set_frame(img)
        w=self.preview_windows.get(cid)
        if w and w.isVisible(): w.set_frame(img)

    def on_packet(self,p):
        try:
            from .protocol import TelemetryPacket
            TelemetryPacket.validate(p); self.sim.apply_packet(p); self.telemetry_mode.setText("EXTERNAL TELEMETRY")
            alarm=p.get("alarm") or {}; target=p.get("target") or {}; cat=str(alarm.get("category",target.get("category","NONE"))).upper(); cid=p.get("camera_id"); state=(cat,bool(alarm.get("active",cat=="SUSPICIOUS")))
            if self._last_alarm_state.get(cid)!=state:
                self._last_alarm_state[cid]=state
                msg=str(alarm.get("message", "")) or ("Suspicious target detected" if cat=="SUSPICIOUS" else f"Target classified {cat}")
                level="ALARM" if state[1] and cat=="SUSPICIOUS" else "INFO"
                self._log(level,f"{cid}: {msg}")
                self._add_alarm_history(cid,target.get("id",self.sim.cameras.get(cid).target_id if cid in self.sim.cameras else "-"),cat,float(alarm.get("confidence",target.get("confidence",0)) or 0),msg,state[1])
        except Exception as e: self._log("ERROR",f"Telemetry: {e}")

    def _add_alarm_history(self,cid,target,category,confidence,message,active):
        row=[time.strftime("%H:%M:%S"),str(cid),str(target or "-"),category,f"{confidence*100:.0f}%",message,"ACTIVE" if active else "INFO"]
        self.alarm_history.insert(0,row); self.alarm_history=self.alarm_history[:200]
        self.alarm_table.setRowCount(len(self.alarm_history))
        for r,vals in enumerate(self.alarm_history):
            for c,v in enumerate(vals):
                item=QTableWidgetItem(v); self.alarm_table.setItem(r,c,item)
        self.alarm_table.resizeRowsToContents()

    def on_update(self,cameras,targets):
        # Keep the latest telemetry so a lazily-created Map tab can immediately
        # initialize from current state. Telemetry never controls the viewport.
        self._last_cameras = cameras
        self._last_targets = targets
        self.monitor_map.set_state(cameras,targets); self.monitor_map.select_camera(self.selected_id, center=False)
        if hasattr(self, "map"):
            self.map.set_state(cameras,targets); self.map.select_camera(self.selected_id, center=False)
        online=sum(c.status=="ONLINE" for c in cameras.values()); self.status_labels["Active Cameras"].setText(f"{online} / {len(cameras)}")
        active=[c for c in cameras.values() if c.alarm_active and c.alarm_category=="SUSPICIOUS"]
        self.status_labels["Alarms"].setText(f"{len(active)} ACTIVE")
        self.active_alarm_count.setText(str(len(active))); self.suspicious_count.setText(str(sum(c.alarm_category=="SUSPICIOUS" for c in cameras.values()))); self.friendly_count.setText(str(sum(c.alarm_category=="FRIENDLY" for c in cameras.values())))
        self.global_alarm.setText("● SUSPICIOUS ALARM ACTIVE" if active else "● NO ACTIVE ALARMS"); self.global_alarm.setStyleSheet("color:#fecaca;font-weight:700" if active else "color:#35d07f;font-weight:700")
        for c in cameras.values():
            for i in range(self.camera_list.count()):
                it=self.camera_list.item(i)
                if it.data(Qt.UserRole)==c.id: it.setText(f"●  {c.id}  -  {c.name}\n    {c.status}  |  {c.target_id or 'TARGET'} | {c.alarm_category}")
            for i in range(self.camera_page_list.count()):
                it=self.camera_page_list.item(i)
                if it.data(Qt.UserRole)==c.id: it.setText(f"●  {c.id}  -  {c.name}\n    {c.status} | {c.alarm_category}")
            if c.id in self.video_cards: self.video_cards[c.id].set_alarm(c.alarm_category)
            if c.id in self.camera_page_cards: self.camera_page_cards[c.id].set_alarm(c.alarm_category)
        self._refresh_asset_cards()
        c=cameras[self.selected_id]
        self.tel_info.setText(f"GPS {c.lat:.5f},{c.lon:.5f} | HDG {c.heading_deg:.1f}° | RNG {c.range_m:.1f} m" if c.range_m else f"GPS {c.lat:.5f},{c.lon:.5f} | HDG {c.heading_deg:.1f}°")
        self.alarm_info.setText(f"Alarm: {c.alarm_category} | Confidence: {c.alarm_confidence*100:.0f}%" + (f" | {c.alarm_message}" if c.alarm_message else "")); self.connection.setText("● Telemetry Active" if self.sim.external_mode else "● Simulation Active")

    def _log(self,level,msg):
        it=QListWidgetItem(f"{time.strftime('%H:%M:%S')}   {level:<7}   {msg}"); self.log.insertItem(0,it); self.alarm_log.insertItem(0,QListWidgetItem(it.text()))
        while self.log.count()>14: self.log.takeItem(self.log.count()-1)
        while self.alarm_log.count()>500: self.alarm_log.takeItem(self.alarm_log.count()-1)

    def _tick(self): self.clock.setText(time.strftime("%Y-%m-%d  %H:%M:%S"))

    def closeEvent(self,e):
        self.sim.stop(); self.telemetry.stop()
        for m in (getattr(self, "monitor_map", None), getattr(self, "map", None)):
            if m:
                m.close()
        for s in self.video_sources.values(): s.close()
        for w in self.preview_windows.values():
            if w: w.close()
        e.accept()
