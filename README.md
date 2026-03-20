# Custom Motorsport Dashboard

A self-contained Python dashboard platform for Raspberry Pi 5 and LattePanda IOTA that combines:

- a browser-based no-code dashboard editor,
- drag/drop + resize widget placement,
- CAN-ID based widget configuration,
- per-widget colors, borders, backgrounds, and alerts,
- a runtime view fed by live CAN or a built-in simulator.

## Why this stack

This project uses Python plus a built-in web server and a vanilla HTML/CSS/JS front end so it stays lightweight and portable across ARM64 Raspberry Pi 5 systems and x86 LattePanda hardware. For live CAN, the app can use `python-can` when available. Without hardware connected, it runs in virtual/simulated mode.

## Features

- **Dashboard editor** with drag-and-drop placement, resize handles, dashboard fullscreen mode that locks widget editing, and draggable label/value positioning inside each widget.
- **No-code widget setup** through a right-side properties panel with per-widget save.
- **CAN-driven widgets** configured by CAN ID, start byte, byte length, scaling, offset, endianness, signedness, units, and fallback values.
- **Per-widget styling** including label, value formatting, colors, borders, radius, uploaded background images, and configurable gauge gradients / tick marks.
- **Per-widget alerts** with readable condition phrases, thresholds, colors, custom warning text, and widget-only / dashboard-background flash / full-screen flash / full-screen solid alert behaviors.
- **Built-in CAN simulator** so you can validate layouts before wiring the real bus.
- **Persistent configuration** saved to `dashboard_config.json`, plus JSON config import support and uploaded image storage inside the saved config.

## Quick start

```bash
python3 -m src.dashboard_app --host 0.0.0.0 --port 8765
```

Then open `http://localhost:8765` in a browser on the target device.

## Optional live CAN support

Install `python-can` for live CAN interfaces:

```bash
python3 -m pip install python-can
```

The dashboard uses the CAN settings stored in the configuration file. The default configuration starts in `virtual` mode for easy testing.

## Project layout

- `src/dashboard_app.py` — HTTP server, config persistence, CAN reader/simulator, and decoding logic.
- `static/index.html` — dashboard builder UI.
- `static/styles.css` — editor and widget styling.
- `static/app.js` — client-side state, drag/drop editing, runtime polling, and form binding.
- `tests/test_dashboard_app.py` — decoding and alert tests.

## Notes for real deployments

- Raspberry Pi 5 commonly uses Linux SocketCAN adapters or HATs.
- LattePanda IOTA can run this stack on Linux; on Windows you may need a CAN interface supported by `python-can`.
- Background images can be local files served by another endpoint or hosted image URLs. For a production in-car deployment, you would normally store these assets locally and extend the static asset handling.
