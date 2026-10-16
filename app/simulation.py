
import math, random, time, yaml
from PySide6.QtCore import QObject,QTimer,Signal
from .models import CameraState,TargetState,ALARM_CATEGORIES,CATEGORY_COLORS
from .geo import haversine_m,bearing_deg,elevation_deg

class SimulationManager(QObject):
    updated=Signal(object,object)
    def __init__(self,config_path):
        super().__init__()
        with open(config_path,encoding="utf-8") as f: self.cfg=yaml.safe_load(f)
        self.cameras={}
        for raw in self.cfg["cameras"]:
            c=dict(raw)
            # Backward-compatible scenario fields: target classification belongs
            # to the target/alarm state, not to CameraState itself.
            target_category=str(c.pop("target_category", "NONE")).upper()
            target_confidence=float(c.pop("target_confidence", 0.0) or 0.0)
            alarm_message=str(c.pop("alarm_message", ""))
            c["alarm_category"] = target_category if target_category in ALARM_CATEGORIES else "NONE"
            c["alarm_confidence"] = max(0.0, min(1.0, target_confidence))
            c["alarm_message"] = alarm_message
            self.cameras[c["id"]]=CameraState(**c)
        self.targets={t["id"]:TargetState(**t) for t in self.cfg["targets"]}
        self.selected_camera=next(iter(self.cameras)); self.running=False; self.external_mode=False
        self.last=time.monotonic()
        self.timer=QTimer(); self.timer.setInterval(int(1000/self.cfg["simulation"]["update_hz"])); self.timer.timeout.connect(self.step)
        self.calculate()
    def start(self): self.running=True; self.last=time.monotonic(); self.timer.start()
    def stop(self): self.running=False; self.timer.stop()
    def set_selected_camera(self,cid):
        if cid in self.cameras:self.selected_camera=cid
        self.updated.emit(self.cameras,self.targets)
    def step(self):
        if not self.running:return
        if not self.external_mode:
            now=time.monotonic()
            for i,t in enumerate(self.targets.values()):
                phase=now*.10+i*1.1;t.lat+=math.cos(phase)*.0000025;t.lon+=math.sin(phase)*.0000025
            self.calculate()
        self.updated.emit(self.cameras,self.targets)
    def apply_packet(self,p):
        cid=p.get("camera_id")
        c=self.cameras.get(cid)
        if not c:
            return
        g=p.get("gps",{}); comp=p.get("compass",{}); cam=p.get("camera",{}); tgt=p.get("target") or {}
        c.lat=float(g.get("latitude_deg",c.lat)); c.lon=float(g.get("longitude_deg",c.lon)); c.altitude_m=float(g.get("altitude_m",c.altitude_m))
        c.heading_deg=float(comp.get("heading_deg",c.heading_deg)); c.fov_deg=float(cam.get("fov_deg",c.fov_deg))

        alarm=p.get("alarm") or {}
        category=str(alarm.get("category",tgt.get("category",c.alarm_category or "NONE"))).upper()
        if category not in ALARM_CATEGORIES:
            category="NONE"
        confidence=float(alarm.get("confidence",tgt.get("confidence",0.0)) or 0.0)
        c.alarm_category=category
        c.alarm_confidence=max(0.0,min(1.0,confidence))
        c.alarm_active=bool(alarm.get("active",category=="SUSPICIOUS"))
        c.alarm_message=str(alarm.get("message", ""))

        if tgt and tgt.get("latitude_deg") is not None and tgt.get("longitude_deg") is not None:
            tid=tgt.get("id",c.target_id or f"TGT-{cid.split('-')[-1]}")
            t_category=str(tgt.get("category",category)).upper()
            if t_category not in ALARM_CATEGORIES:
                t_category=category
            t_color=str(tgt.get("color",CATEGORY_COLORS.get(t_category,"#facc15")))
            if tid not in self.targets:
                self.targets[tid]=TargetState(tid,float(tgt["latitude_deg"]),float(tgt["longitude_deg"]),float(tgt.get("altitude_m",0)),t_color,t_category,float(tgt.get("confidence",confidence) or 0.0))
            else:
                t=self.targets[tid];t.lat=float(tgt["latitude_deg"]);t.lon=float(tgt["longitude_deg"]);t.altitude_m=float(tgt.get("altitude_m",t.altitude_m));t.category=t_category;t.confidence=float(tgt.get("confidence",confidence) or 0.0);t.color=t_color
            c.target_id=tid;c.target_lat=self.targets[tid].lat;c.target_lon=self.targets[tid].lon;c.target_altitude_m=self.targets[tid].altitude_m
            # Target classification is the source for the camera alarm unless an explicit alarm object overrides it.
            if not alarm:
                c.alarm_category=t_category
                c.alarm_confidence=max(0.0,min(1.0,self.targets[tid].confidence))
                c.alarm_active=t_category=="SUSPICIOUS"

        rf=p.get("rangefinder") or {}
        if rf.get("valid") and rf.get("distance_m") is not None:
            c.range_m=float(rf["distance_m"]);c.range_valid=True
        c.status="ONLINE"; self.external_mode=True; self.calculate_camera(c)

    def calculate_camera(self,c):
        t=self.targets.get(c.target_id) if c.target_id else None
        if not t:return
        horizontal=haversine_m(c.lat,c.lon,t.lat,t.lon); true=math.hypot(horizontal,t.altitude_m-c.altitude_m)
        cfg=self.cfg["simulation"]; measured=c.range_m if c.range_valid else true+random.gauss(0,cfg["range_noise_stddev_m"])
        c.range_valid=cfg["rangefinder_min_m"]<=measured<=cfg["rangefinder_max_m"];c.range_m=measured if c.range_valid else None
        c.bearing_deg=bearing_deg(c.lat,c.lon,t.lat,t.lon);c.elevation_deg=elevation_deg(c.altitude_m,t.altitude_m,horizontal)
    def calculate(self):
        for i,c in enumerate(self.cameras.values()):
            if c.status=="ONLINE" and self.external_mode and c.target_id: self.calculate_camera(c);continue
            tid=c.target_id or f"TGT-{i+1:02d}";t=self.targets.get(tid)
            if not t:
                c.status="NO TARGET";c.range_valid=False;continue
            c.status="ONLINE";c.target_id=t.id;c.target_lat=t.lat;c.target_lon=t.lon;c.target_altitude_m=t.altitude_m
            c.alarm_category=getattr(t,"category","NONE");c.alarm_confidence=getattr(t,"confidence",0.0);c.alarm_active=c.alarm_category=="SUSPICIOUS"
            horizontal=haversine_m(c.lat,c.lon,t.lat,t.lon);true=math.hypot(horizontal,t.altitude_m-c.altitude_m)
            measured=true+random.gauss(0,self.cfg["simulation"]["range_noise_stddev_m"])
            c.range_valid=self.cfg["simulation"]["rangefinder_min_m"]<=measured<=self.cfg["simulation"]["rangefinder_max_m"];c.range_m=measured if c.range_valid else None
            c.bearing_deg=bearing_deg(c.lat,c.lon,t.lat,t.lon);c.elevation_deg=elevation_deg(c.altitude_m,t.altitude_m,horizontal)
