
"""
CCM Telemetry Protocol simulator.

Run:
    python scripts/inject_simulated_data.py

Real hardware can replace this program by sending the same JSON/UDP packets
to the Central Camera Monitor on UDP port 5010.
"""
import json, math, socket, time, yaml, sys
from pathlib import Path

# Make the project root importable when this file is executed directly from
# either the project root or the scripts directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.protocol import TelemetryPacket

CFG=yaml.safe_load((ROOT/"config"/"scenario.yaml").read_text(encoding="utf-8"))
cams=CFG["cameras"]; targets=CFG["targets"]
target_by_id={t["id"]:t for t in targets}
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
seq={c["id"]:0 for c in cams}

print("CCM telemetry simulator -> UDP 127.0.0.1:5010")
print("Press Ctrl+C to stop.")

while True:
    now=int(time.time()*1000)
    phase=time.time()*0.10
    for i,c in enumerate(cams):
        cid=c["id"]; seq[cid]+=1
        tid=c.get("target_id",f"TGT-{i+1:02d}"); t=target_by_id.get(tid)
        if not t: continue
        lat=t["lat"]+math.cos(phase+i)*0.0000025
        lon=t["lon"]+math.sin(phase+i)*0.0000025
        pkt=TelemetryPacket(
            camera_id=cid, sequence=seq[cid], timestamp_unix_ms=now,
            gps={"latitude_deg":c["lat"],"longitude_deg":c["lon"],"altitude_m":c["altitude_m"],"fix":3,"hdop":0.8},
            compass={"heading_deg":c["heading_deg"],"source":"SIMULATED"},
            camera={"azimuth_deg":c["heading_deg"],"elevation_deg":-20.0,"fov_deg":c["fov_deg"]},
            target={"id":tid,"latitude_deg":lat,"longitude_deg":lon,"altitude_m":t["altitude_m"],"category":c.get("target_category","NONE"),"confidence":float(c.get("target_confidence",0.0))},
            rangefinder={"distance_m":None,"valid":False,"type":"SIMULATED"},
            system={"armed":False,"battery_v":24.1,"link_quality_pct":100},
            video={"source":"FILE","name":f"videos/{cid}.mp4"},
            alarm={"active":c.get("target_category","NONE")=="SUSPICIOUS","category":c.get("target_category","NONE"),"confidence":float(c.get("target_confidence",0.0)),"message":c.get("alarm_message","")}
        )
        sock.sendto(pkt.encode(),("127.0.0.1",5010))
    time.sleep(0.1)
