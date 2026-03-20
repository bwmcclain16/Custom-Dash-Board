# Custom Motorsport Dashboard

An all-in-one motorsport dashboard designer and runtime that runs as a single Python program. It serves a browser-based editor where you can drag and drop widgets, configure dashboard aesthetics, bind widgets directly to CAN IDs, and define per-widget alerts without writing code.

## Highlights

- Drag-and-drop dashboard editor with resize handles.
- Per-widget styling for borders, colors, radius, and optional background images.
- Per-widget CAN configuration: CAN ID, start byte, byte length, signed/unsigned decoding, endianness, scale, offset, precision, demo ranges.
- Per-widget alert rules with custom thresholds, messages, severities, and colors.
- Dashboard-wide theme settings and background image support.
- SocketCAN support for Linux-based deployments on Raspberry Pi 5 and LattePanda IOTA.
- Demo mode for designing dashboards without live CAN hardware.

## Why Python + browser UI

Python is a strong fit here because it runs well on both ARM64 Raspberry Pi 5 and x86 LattePanda systems. The app uses only the Python standard library, plus Linux SocketCAN support through raw CAN sockets, so there are no mandatory dependencies for the included demo mode and editor.

## Quick start

```bash
python3 app.py
```

Then open `http://localhost:8765` in a browser.

Optional environment variables:

```bash
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8765
python3 app.py
```

## CAN setup

1. Start in **Demo** mode to design your layout.
2. Switch the CAN section to **SocketCAN**.
3. Set your interface name, usually `can0`.
4. Save the layout.
5. Ensure your Linux device has a working SocketCAN interface.

Example interface setup on Linux:

```bash
sudo ip link set can0 up type can bitrate 500000
```

## Widget workflow

1. Click **Add Widget**.
2. Select the widget in the widget list.
3. Enter the CAN ID and data extraction settings.
4. Tune colors, borders, value range, and optional background image.
5. Add alert rules for warning or critical thresholds.
6. Drag the widget on the preview canvas and resize it from the bottom-right corner.
7. Click **Save Layout**.

## Data model notes

Each widget decodes a contiguous byte segment from a CAN frame:

- `CAN ID`: Frame arbitration ID to listen for.
- `Start Byte`: First byte index in the frame.
- `Length`: Number of bytes to decode.
- `Endianness`: Big or little endian.
- `Signed`: Treat the raw value as signed or unsigned.
- `Scale` and `Offset`: Convert raw data into engineering units.
- `Precision`: Display decimal places.

## Files

- `app.py`: HTTP server, config storage, SocketCAN/demo data acquisition, widget value decoding.
- `static/index.html`: UI layout.
- `static/styles.css`: Styling for editor and dashboard preview.
- `static/app.js`: Drag/drop editor, widget customization, live preview refresh.
- `data/config.json`: Saved configuration, generated on first run.

## Future upgrade ideas

- Add DBC import support.
- Add chart and bar widgets.
- Support multiple dashboards/profiles.
- Add touchscreen-specific controls.
- Add authentication for networked use.
