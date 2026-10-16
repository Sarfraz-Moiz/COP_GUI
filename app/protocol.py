from __future__ import annotations
from dataclasses import dataclass, asdict
import json

PROTOCOL_NAME = "CCM-TELEMETRY"
PROTOCOL_VERSION = "1.0"
ALARM_CATEGORIES = ("NONE", "FRIENDLY", "SUSPICIOUS")

@dataclass
class TelemetryPacket:
    camera_id: str
    sequence: int
    timestamp_unix_ms: int
    gps: dict
    compass: dict
    camera: dict
    target: dict | None = None
    rangefinder: dict | None = None
    system: dict | None = None
    video: dict | None = None
    alarm: dict | None = None

    def to_dict(self):
        d = asdict(self)
        d["protocol"] = {"name": PROTOCOL_NAME, "version": PROTOCOL_VERSION}
        return d

    def encode(self):
        return (json.dumps(self.to_dict(), separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def validate(d: dict):
        p = d.get("protocol", {})
        required = ["camera_id", "sequence", "timestamp_unix_ms", "gps", "compass", "camera"]
        if p.get("name") != PROTOCOL_NAME or p.get("version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported telemetry protocol")
        for k in required:
            if k not in d:
                raise ValueError(f"Missing field: {k}")

        target = d.get("target") or {}
        category = str(target.get("category", "NONE")).upper()
        alarm = d.get("alarm") or {}
        alarm_category = str(alarm.get("category", category)).upper()
        if category not in ALARM_CATEGORIES:
            raise ValueError(f"Unsupported target category: {category}")
        if alarm_category not in ALARM_CATEGORIES:
            raise ValueError(f"Unsupported alarm category: {alarm_category}")
        if "confidence" in target and not 0.0 <= float(target["confidence"]) <= 1.0:
            raise ValueError("Target confidence must be between 0 and 1")
        return d
