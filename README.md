# Custom Motorsport Dashboard

A cross-platform desktop dashboard editor and runtime for motorsport data received over CAN. The application is designed to run on both Raspberry Pi 5 and LattePanda IOTA using Python and Qt, giving you one all-in-one program for editing layouts, configuring widgets, and displaying live vehicle data.

## What it includes

- Drag-and-drop style dashboard workflow with a widget library and visual canvas.
- Per-widget CAN setup using arbitration ID, byte offset, byte length, scale, offset, units, signed/unsigned, and endianness.
- Per-widget appearance controls including border color, border width, border radius, text color, background color, and optional background images.
- Per-widget alert rules so each widget can trigger its own custom warning label, colors, and border state based on decoded CAN values.
- Dashboard-wide theme editing for title, canvas colors, grid size, snap-to-grid behavior, and background image.
- Save/load support using JSON so the same dashboard file can be moved between devices.
- Simulation mode by default (`virtual` CAN) so you can design screens before wiring hardware.

## Why Python + PySide6

Python with PySide6 is a good fit here because it is:

- Cross-platform for ARM64/Linux on Raspberry Pi 5 and x86/Windows or Linux on LattePanda IOTA.
- Fast to iterate on for UI-heavy tooling.
- Easy to connect to SocketCAN, virtual CAN, or other `python-can` back ends later.
- Deployable as a single packaged app with tools like PyInstaller or Briefcase if you want kiosk-style installs.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
motorsport-dashboard
```

## Using the dashboard editor

1. Launch the app.
2. Double-click a widget type in the **Widget Library**.
3. Click the widget on the canvas.
4. Use the **Widget Setup** panel to configure:
   - widget type and label
   - widget size and position
   - colors, borders, warning text, and background image
   - CAN ID, byte extraction, scale, offset, min/max, and units
5. Add custom alert rules in the **Alert Rules** section for things like shift RPM, coolant temp, oil pressure, lambda, or battery voltage.
6. Save the dashboard to JSON and reuse it on another system.

## CAN notes

The app starts in simulation mode using `virtual` CAN when no hardware is configured. For real hardware you can change the dashboard config values for interface, channel, and bitrate, then update the `CanBusManager` connection to match your adapter/back end.

Common Linux examples with `python-can` include:

- `socketcan` for Raspberry Pi CAN HATs or USB CAN adapters.
- `pcan`, `kvaser`, or `slcan` if the installed hardware supports those back ends.

## Project structure

- `src/motorsport_dashboard/models.py` – dashboard, widget, signal, and alert configuration models.
- `src/motorsport_dashboard/can_bus.py` – CAN connection handling and simulation mode.
- `src/motorsport_dashboard/ui.py` – Qt-based editor, canvas, inspector, and runtime display logic.
- `src/motorsport_dashboard/app.py` – application entry point.
- `tests/test_models.py` – basic regression tests for decoding, serialization, and alerts.

## Next enhancements you may want

- Additional widget types such as circular gauges, shift lights, lap delta, and track maps.
- A dedicated runtime/kiosk mode separate from the editor.
- More advanced drag/resize handles and alignment tools.
- Import/export presets for common ECUs.
- Authentication or locking for race-day deployments.
