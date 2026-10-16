# Central Camera Monitor

A general-purpose desktop central camera monitoring COP application with:

- Real interactive map using an isolated **Leaflet + Qt WebEngine map engine**.
- Map center driven by the latest camera GPS telemetry — no hard-coded geographic location.
- Explicit Street, Satellite and Hybrid tile providers, isolated from QGroundControl.
- Camera, target, heading, camera-to-target link and FOV overlays.
- FILE/REPLAY, RTSP, USB and built-in camera sources.
- UDP `CCM-TELEMETRY v1.0` input for simulated or future real telemetry.

## Map behavior

The map is intentionally location-agnostic. The application does not contain a fixed operational site. When telemetry is injected, the map centers on the selected camera and displays the injected camera/target coordinates.

The V7 map engine no longer uses Qt Location's generic OSM provider. That provider can select third-party repositories such as Thunderforest and may expose only the map types that the provider supports. Instead, the CCM map uses an isolated Leaflet/Qt WebEngine renderer with explicit Street, Satellite and Hybrid tile sources.

This is intentionally independent of the QGroundControl installation. It follows the useful QGC model of explicit map providers and map modes without linking our Python application against QGC's custom C++ Qt Location plugin.

**Tile usage note:** the selected tile provider's terms must permit the intended operational use and any bulk/offline download. The application does not bypass provider authentication or licensing.

## Run

```bat
conda activate copSim
python main.py
```

In another terminal, from the project root:

```bat
conda activate copSim
python scripts\inject_simulated_data.py
```

The injector now adds the project root to `sys.path`, so it can also be run directly from the `scripts` directory.

## Real system integration

Keep sending `CCM-TELEMETRY v1.0` packets with real GPS coordinates. No map code needs to be changed. The map consumes the same `camera_id`, `gps.latitude_deg`, `gps.longitude_deg`, target GPS, heading, FOV and rangefinder fields used by the simulator.

## Telemetry Simulator GUI
Use the telemetry test injector (`python scripts\simulation_gui.py`) to edit and inject camera/target telemetry, including target category (`NONE`, `FRIENDLY`, `SUSPICIOUS`) and alarm data. The GUI supports one-shot and continuous UDP injection.

## V6 operator views

The operator UI is organized into five views:

- Monitor — combined situational dashboard.
- Map — full-screen operational map with Street/Satellite selector.
- Cameras — dedicated camera wall; click any preview for an expanded window.
- Alarms & Logs — alarm/classification history plus system event log.
- Settings — protocol and architecture summary.

The map selector uses explicit `Street`, `Satellite` and `Hybrid` layers. Satellite imagery is provided independently of Qt Location, so the UI no longer depends on the generic OSM plugin's satellite capabilities.

## Assets COP
The Assets view provides checkpost-level UAV availability, camera-derived target information, and a training/coordination tasking dialog. Engagement requests are recorded locally only; no flight or weapon command is transmitted.
