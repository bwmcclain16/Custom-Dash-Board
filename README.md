# Custom Motorsport Dashboard

A cross-platform CAN dashboard editor designed for Raspberry Pi 5 and LattePanda-class devices. The application runs as a single Python program with a browser-based UI, so the same codebase can drive a touchscreen dashboard on ARM or x86 hardware.

## What it does

- Reads live CAN frames with an optional `python-can` backend, with a built-in **demo/virtual** mode for development.
- Lets you create widgets by entering a CAN ID, byte offset, byte length, type, scaling, offset, and endianness.
- Provides a drag-and-drop dashboard canvas so widgets can be placed visually instead of coded by hand.
- Supports per-widget styling: colors, border visibility, border width, border radius, font sizes, accent colors, and background images.
- Supports per-widget alert rules so any widget can show custom warnings using thresholds.
- Stores dashboard layout and widget settings in `dashboard-config.json`.

## Recommended architecture

This implementation uses:

- **Python standard library HTTP server** for the all-in-one backend and static file server.
- **Vanilla HTML/CSS/JS** for a lightweight editor that works well on low-power single-board computers.
- **Optional `python-can`** integration for CAN transport abstraction, allowing you to start with virtual/demo data and switch to real interfaces later.

This is a good fit for Raspberry Pi 5 and LattePanda IOTA because it:

- avoids heavyweight Electron packaging,
- runs on Linux ARM64 and x86_64 with Python 3.10+, and
- can be opened fullscreen in Chromium, Edge, or another kiosk browser.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m app.main
```

Then open <http://127.0.0.1:8000>.

## Configuring CAN input

The UI contains a **CAN Bus** section where you can choose:

- interface name, such as `socketcan`, `pcan`, or `virtual`,
- channel, such as `can0`, and
- bitrate.

For Linux on a Raspberry Pi, a typical setup is:

```bash
sudo ip link set can0 up type can bitrate 500000
python -m app.main
```

Then set the bus in the UI to:

- Interface: `socketcan`
- Channel: `can0`
- Bitrate: `500000`

## Example widget workflows

1. Click **Add widget**.
2. Select the widget type, such as value, gauge, bar, or status.
3. Enter the CAN ID and byte mapping.
4. Tune scale, offset, unit, and min/max range.
5. Set colors, border, and background image.
6. Add one or more alert rules.
7. Drag the widget onto the dashboard canvas.
8. Click **Save layout**.

## Notes and next steps

This scaffold is intentionally open-ended so you can extend it with:

- custom widget libraries,
- multi-page dashboards,
- chart/history widgets,
- touchscreen-only editing gestures,
- user accounts/profile presets,
- import/export of DBC-derived signal definitions.
