# CCM-TELEMETRY v1.0

Transport: UDP
Default receiver: `0.0.0.0:5010`
Encoding: UTF-8 JSON, one packet per UDP datagram.

## Target classification / alarm

The target classification is carried in `target.category` and is one of:

- `NONE` — no classified alarm condition.
- `FRIENDLY` — target is identified/declared friendly.
- `SUSPICIOUS` — target requires attention and is treated as an active alarm by the central UI.

`target.confidence` is optional and ranges from `0.0` to `1.0`.

An optional top-level `alarm` object carries the current alarm state from the camera/edge system. When present, it is:

```json
{
  "alarm": {
    "active": true,
    "category": "SUSPICIOUS",
    "confidence": 0.87,
    "message": "Unverified target"
  }
}
```

The central application accepts `NONE`, `FRIENDLY`, and `SUSPICIOUS`. The UI raises the global active-alarm indicator when a camera reports `SUSPICIOUS` with an active alarm.

## Packet

```json
{
  "protocol":{"name":"CCM-TELEMETRY","version":"1.0"},
  "camera_id":"CAM-01",
  "sequence":123,
  "timestamp_unix_ms":1770000000000,
  "gps":{"latitude_deg":28.315,"longitude_deg":67.445,"altitude_m":95.0,"fix":3,"hdop":0.8},
  "compass":{"heading_deg":35.0,"source":"MAGNETOMETER"},
  "camera":{"azimuth_deg":35.0,"elevation_deg":-20.0,"fov_deg":55.0},
  "target":{"id":"TGT-01","latitude_deg":28.3000,"longitude_deg":67.4550,"altitude_m":20.0,"category":"SUSPICIOUS","confidence":0.87},
  "rangefinder":{"distance_m":1250.2,"valid":true,"type":"LASER"},
  "system":{"armed":false,"battery_v":24.1,"link_quality_pct":98},
  "video":{"source":"RTSP","name":"rtsp://camera/stream"},
  "alarm":{"active":true,"category":"SUSPICIOUS","confidence":0.87,"message":"Unverified target"}
}
```

Existing v1.0 packets remain compatible because `target.category`, `target.confidence`, and `alarm` are optional additions.

`camera_id` is the stable identity used to join telemetry, video and map objects.
`sequence` is monotonically increasing per camera.
`timestamp_unix_ms` is the source timestamp.
Angles are degrees. GPS is WGS84 decimal degrees. Altitude is metres.

## Simulator GUI

Run:

```bat
python scripts\simulation_gui.py
```

The GUI provides editable fields for destination, camera GPS, heading/FOV, target position, classification, confidence, alarm message, rangefinder, system state, and video source. It can send one packet or continuously inject packets at a selectable rate.
