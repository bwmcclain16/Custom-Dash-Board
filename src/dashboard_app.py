from __future__ import annotations

import argparse
import json
import math
import mimetypes
import threading
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import can  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    can = None

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
CONFIG_PATH = BASE_DIR / "dashboard_config.json"

DEFAULT_DASHBOARD = {
    "name": "Motorsport Command Center",
    "width": 1280,
    "height": 720,
    "backgroundColor": "#08111f",
    "backgroundImage": "",
    "gridSize": 16,
    "showGrid": True,
    "fontFamily": "Inter, Arial, sans-serif",
}

DEFAULT_CAN = {
    "interface": "virtual",
    "channel": "motorsport-dashboard",
    "bitrate": 500000,
    "dbc": "",
    "pollIntervalMs": 100,
}

DEFAULT_SOURCE = {
    "canId": "0x100",
    "startByte": 0,
    "byteLength": 1,
    "endian": "little",
    "signed": False,
    "scale": 1,
    "offset": 0,
    "units": "",
    "samplePeriodMs": 100,
    "fallback": 0,
    "valueMap": {},
}

DEFAULT_DISPLAY = {
    "label": "Widget",
    "decimalPlaces": 0,
    "prefix": "",
    "suffix": "",
    "min": 0,
    "max": 100,
    "backgroundColor": "#132033",
    "textColor": "#f8fafc",
    "accentColor": "#38bdf8",
    "borderColor": "#38bdf8",
    "borderWidth": 2,
    "borderRadius": 20,
    "backgroundImage": "",
    "showLabel": True,
    "showValue": True,
}

DEFAULT_ALERT = {
    "id": "alert-default",
    "name": "Warning",
    "operator": "greater_or_equal",
    "threshold": 90,
    "color": "#ef4444",
    "message": "WARNING",
}

DEFAULT_WIDGET = {
    "id": "widget-default",
    "name": "Widget",
    "kind": "value",
    "x": 80,
    "y": 80,
    "w": 220,
    "h": 160,
    "z": 1,
    "source": DEFAULT_SOURCE,
    "display": DEFAULT_DISPLAY,
    "alerts": [DEFAULT_ALERT],
}

DEFAULT_CONFIG: dict[str, Any] = {
    "dashboard": DEFAULT_DASHBOARD,
    "can": DEFAULT_CAN,
    "widgets": [
        {
            "id": "widget-rpm",
            "name": "Engine RPM",
            "kind": "gauge",
            "x": 48,
            "y": 48,
            "w": 300,
            "h": 220,
            "z": 1,
            "source": {
                **DEFAULT_SOURCE,
                "canId": "0x100",
                "byteLength": 2,
                "units": "rpm",
                "samplePeriodMs": 50,
            },
            "display": {
                **DEFAULT_DISPLAY,
                "label": "RPM",
                "max": 12000,
                "backgroundColor": "rgba(4,16,30,0.84)",
                "borderColor": "#60a5fa",
                "borderRadius": 24,
            },
            "alerts": [
                {
                    "id": "alert-high-rpm",
                    "name": "Over-rev",
                    "operator": "greater_or_equal",
                    "threshold": 10500,
                    "color": "#ef4444",
                    "message": "SHIFT NOW",
                }
            ],
        },
        {
            "id": "widget-coolant",
            "name": "Coolant Temp",
            "kind": "value",
            "x": 380,
            "y": 78,
            "w": 240,
            "h": 180,
            "z": 2,
            "source": {
                **DEFAULT_SOURCE,
                "canId": "0x101",
                "startByte": 2,
                "units": "°C",
                "offset": -40,
            },
            "display": {
                **DEFAULT_DISPLAY,
                "label": "Coolant",
                "max": 140,
                "backgroundColor": "rgba(15,23,42,0.86)",
                "accentColor": "#22c55e",
                "borderColor": "#22c55e",
            },
            "alerts": [
                {
                    "id": "alert-high-temp",
                    "name": "Temp Warning",
                    "operator": "greater_or_equal",
                    "threshold": 110,
                    "color": "#f97316",
                    "message": "COOLANT HOT",
                }
            ],
        },
    ],
}


@dataclass
class FrameRecord:
    arbitration_id: int
    data: list[int]
    timestamp: float = field(default_factory=time.time)


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.config = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            return normalize_config(json.loads(self.path.read_text()))
        config = normalize_config(deepcopy(DEFAULT_CONFIG))
        self.path.write_text(json.dumps(config, indent=2))
        return config

    def get(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.config))

    def save(self, new_config: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.config = normalize_config(new_config)
            self.path.write_text(json.dumps(self.config, indent=2))
            return json.loads(json.dumps(self.config))


class CanMonitor:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.lock = threading.Lock()
        self.frames: dict[int, FrameRecord] = {}
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.status = "simulated"
        self.error = ""

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        config = self.config_store.get().get("can", {})
        interface = config.get("interface", "virtual")
        channel = config.get("channel", "motorsport-dashboard")
        bitrate = int(config.get("bitrate", 500000))
        if can is None or interface == "virtual":
            self.status = "simulated"
            self.error = "python-can unavailable or virtual mode selected"
            self._simulate_loop()
            return
        try:
            bus = can.Bus(interface=interface, channel=channel, bitrate=bitrate)
            self.status = f"live:{interface}:{channel}"
            self.error = ""
            while not self.stop_event.is_set():
                message = bus.recv(timeout=0.25)
                if message is None:
                    continue
                self.inject_frame(message.arbitration_id, list(message.data), message.timestamp)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.status = "simulated"
            self.error = f"CAN fallback engaged: {exc}"
            self._simulate_loop()

    def _simulate_loop(self) -> None:
        phase = 0.0
        while not self.stop_event.is_set():
            rpm = int(2800 + 1800 * (1 + math.sin(phase)))
            coolant = int(72 + 12 * (1 + math.sin(phase / 3.0)))
            self.inject_frame(0x100, [rpm & 0xFF, (rpm >> 8) & 0xFF, 0, 0, 0, 0, 0, 0])
            self.inject_frame(0x101, [0, 0, max(0, coolant + 40), 0, 0, 0, 0, 0])
            phase += 0.08
            time.sleep(0.1)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

    def inject_frame(self, arbitration_id: int, data: list[int], timestamp: float | None = None) -> None:
        with self.lock:
            self.frames[arbitration_id] = FrameRecord(
                arbitration_id=arbitration_id,
                data=data[:8],
                timestamp=timestamp or time.time(),
            )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {f"0x{frame_id:X}": asdict(record) for frame_id, record in sorted(self.frames.items())}

    def decode_widget(self, widget: dict[str, Any]) -> dict[str, Any]:
        source = widget.get("source", {})
        can_id = parse_can_id(source.get("canId", "0"))
        fallback = source.get("fallback", 0)
        with self.lock:
            frame = self.frames.get(can_id)
        if not frame:
            value = fallback
            updated_at = None
        else:
            value = decode_signal(frame.data, source)
            updated_at = frame.timestamp
        alert = evaluate_alerts(value, widget.get("alerts", []))
        display = widget.get("display", {})
        decimals = int(display.get("decimalPlaces", 0))
        suffix = display.get("suffix", "") or source.get("units", "")
        formatted = f"{display.get('prefix', '')}{value:.{decimals}f}{suffix}"
        return {
            "widgetId": widget.get("id"),
            "value": value,
            "formatted": formatted,
            "updatedAt": updated_at,
            "alert": alert,
        }


def deep_merge(defaults: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "dashboard": deep_merge(DEFAULT_DASHBOARD, config.get("dashboard", {})),
        "can": deep_merge(DEFAULT_CAN, config.get("can", {})),
        "widgets": [],
    }
    widgets = config.get("widgets", []) or []
    for index, widget in enumerate(widgets, start=1):
        normalized_widget = deep_merge(DEFAULT_WIDGET, widget)
        normalized_widget["z"] = int(normalized_widget.get("z", index))
        normalized_widget["id"] = str(normalized_widget.get("id") or f"widget-{index}")
        normalized_widget["name"] = str(normalized_widget.get("name") or f"Widget {index}")
        normalized_widget["alerts"] = normalize_alerts(normalized_widget.get("alerts", []), normalized_widget["id"])
        normalized["widgets"].append(normalized_widget)
    if not normalized["widgets"]:
        normalized["widgets"] = deepcopy(DEFAULT_CONFIG["widgets"])
    return normalized


def normalize_alerts(alerts: list[dict[str, Any]], widget_id: str) -> list[dict[str, Any]]:
    normalized_alerts: list[dict[str, Any]] = []
    for index, alert in enumerate(alerts or [DEFAULT_ALERT], start=1):
        normalized_alert = deep_merge(DEFAULT_ALERT, alert)
        normalized_alert["id"] = str(normalized_alert.get("id") or f"{widget_id}-alert-{index}")
        normalized_alert["operator"] = normalize_operator(normalized_alert.get("operator", DEFAULT_ALERT["operator"]))
        normalized_alerts.append(normalized_alert)
    return normalized_alerts or [deepcopy(DEFAULT_ALERT)]


OPERATOR_ALIASES = {
    ">": "greater_than",
    ">=": "greater_or_equal",
    "<": "less_than",
    "<=": "less_or_equal",
    "==": "equal_to",
    "!=": "not_equal_to",
    "greater_than": "greater_than",
    "greater_or_equal": "greater_or_equal",
    "less_than": "less_than",
    "less_or_equal": "less_or_equal",
    "equal_to": "equal_to",
    "not_equal_to": "not_equal_to",
}


def normalize_operator(value: str) -> str:
    return OPERATOR_ALIASES.get(str(value), "greater_or_equal")


def parse_can_id(value: str | int) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    return int(text, 16 if text.startswith("0x") else 10)


def decode_signal(data: list[int], source: dict[str, Any]) -> float:
    start = int(source.get("startByte", 0))
    length = max(1, int(source.get("byteLength", 1)))
    endian = source.get("endian", "little")
    signed = bool(source.get("signed", False))
    scale = float(source.get("scale", 1))
    offset = float(source.get("offset", 0))
    chunk = bytes((data + [0] * 8)[start : start + length])
    raw = int.from_bytes(chunk, byteorder=endian, signed=signed)
    mapped = source.get("valueMap", {}) or {}
    mapped_value = mapped.get(str(raw))
    if mapped_value is not None:
        try:
            return float(mapped_value)
        except (TypeError, ValueError):
            return raw * scale + offset
    return raw * scale + offset


def evaluate_alerts(value: float, alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    operations = {
        "greater_than": lambda a, b: a > b,
        "greater_or_equal": lambda a, b: a >= b,
        "less_than": lambda a, b: a < b,
        "less_or_equal": lambda a, b: a <= b,
        "equal_to": lambda a, b: a == b,
        "not_equal_to": lambda a, b: a != b,
    }
    for alert in alerts:
        operator = normalize_operator(alert.get("operator", DEFAULT_ALERT["operator"]))
        threshold = float(alert.get("threshold", 0))
        if operations[operator](value, threshold):
            alert_copy = deepcopy(alert)
            alert_copy["operator"] = operator
            return alert_copy
    return None


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "MotorsportDashboard/1.1"

    @property
    def app(self) -> "DashboardServer":
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._json_response(self.app.config_store.get())
            return
        if parsed.path == "/api/runtime":
            config = self.app.config_store.get()
            widget_values = [self.app.can_monitor.decode_widget(widget) for widget in config.get("widgets", [])]
            self._json_response(
                {
                    "config": config,
                    "status": self.app.can_monitor.status,
                    "error": self.app.can_monitor.error,
                    "frames": self.app.can_monitor.snapshot(),
                    "widgets": widget_values,
                    "time": time.time(),
                }
            )
            return
        if parsed.path == "/api/frames":
            self._json_response(self.app.can_monitor.snapshot())
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/inject":
            payload = self._read_json()
            self.app.can_monitor.inject_frame(parse_can_id(payload["canId"]), payload.get("data", []))
            self._json_response({"ok": True, "frames": self.app.can_monitor.snapshot()})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            payload = self._read_json()
            saved = self.app.config_store.save(payload)
            self._json_response(saved)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _json_response(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str) -> None:
        clean_path = path.lstrip("/") or "index.html"
        candidate = (STATIC_DIR / clean_path).resolve()
        if STATIC_DIR not in candidate.parents and candidate != STATIC_DIR / "index.html":
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.exists() or candidate.is_dir():
            candidate = STATIC_DIR / "index.html"
        content = candidate.read_bytes()
        mime, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], app: "Application"):
        super().__init__(server_address, handler)
        self.app = app


class Application:
    def __init__(self) -> None:
        self.config_store = ConfigStore(CONFIG_PATH)
        self.can_monitor = CanMonitor(self.config_store)

    def run(self, host: str, port: int) -> None:
        self.can_monitor.start()
        server = DashboardServer((host, port), DashboardRequestHandler, self)
        print(f"Motorsport dashboard running at http://{host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.can_monitor.stop()
            server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Custom motorsport dashboard server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Application().run(args.host, args.port)


if __name__ == "__main__":
    main()
