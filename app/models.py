from dataclasses import dataclass
from typing import Optional

ALARM_CATEGORIES = ("NONE", "FRIENDLY", "SUSPICIOUS")

CATEGORY_COLORS = {
    "NONE": "#64748b",
    "FRIENDLY": "#22c55e",
    "SUSPICIOUS": "#ef4444",
}

@dataclass
class TargetState:
    id: str
    lat: float
    lon: float
    altitude_m: float
    color: str = "#facc15"
    category: str = "NONE"
    confidence: float = 0.0

@dataclass
class CameraState:
    id: str
    name: str
    lat: float
    lon: float
    altitude_m: float
    heading_deg: float
    fov_deg: float
    color: str
    status: str = "ONLINE"
    range_m: Optional[float] = None
    bearing_deg: Optional[float] = None
    elevation_deg: Optional[float] = None
    target_id: Optional[str] = None
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    target_altitude_m: Optional[float] = None
    range_valid: bool = False
    alarm_category: str = "NONE"
    alarm_active: bool = False
    alarm_confidence: float = 0.0
    alarm_message: str = ""
