#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import math
import os
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "settings": {
        "dashboardName": "Motorsport Dashboard",
        "theme": {
            "backgroundColor": "#0b1020",
            "gridColor": "rgba(255,255,255,0.08)",
            "cardColor": "rgba(15,23,42,0.88)",
            "textColor": "#f8fafc",
            "accentColor": "#38bdf8",
            "backgroundImage": "",
            "showGrid": True,
        },
        "can": {
            "mode": "demo",
            "channel": "can0",
            "bustype": "socketcan",
            "bitrate": 500000,
        },
        "refreshMs": 120,
        "snapToGrid": True,
        "gridSize": 20,
    },
    "widgets": [
        {
            "id": "widget-rpm",
            "type": "gauge",
            "title": "Engine RPM",
            "unit": "rpm",
            "position": {"x": 40, "y": 40, "w": 240, "h": 170},
            "style": {
                "backgroundColor": "rgba(15,23,42,0.92)",
                "textColor": "#f8fafc",
                "valueColor": "#38bdf8",
                "borderColor": "#38bdf8",
                "borderWidth": 2,
                "borderRadius": 18,
                "backgroundImage": "",
                "fontFamily": "Inter, sans-serif",
            },
            "data": {
                "canId": "0x101",
                "startByte": 0,
                "length": 2,
                "endianness": "big",
                "signed": False,
                "scale": 1,
                "offset": 0,
                "precision": 0,
                "min": 0,
                "max": 10000,
                "demoMin": 1200,
                "demoMax": 9200,
            },
            "alerts": [
                {
                    "id": "rpm-redline",
                    "label": "Redline",
                    "operator": ">=",
                    "value": 8500,
                    "severity": "critical",
                    "message": "Shift now",
                    "color": "#ef4444",
                }
            ],
        },
        {
            "id": "widget-temp",
            "type": "numeric",
            "title": "Coolant Temp",
            "unit": "°C",
            "position": {"x": 320, "y": 60, "w": 210, "h": 130},
            "style": {
                "backgroundColor": "rgba(30,41,59,0.92)",
                "textColor": "#e2e8f0",
                "valueColor": "#f97316",
                "borderColor": "#f97316",
                "borderWidth": 2,
                "borderRadius": 18,
                "backgroundImage": "",
                "fontFamily": "Inter, sans-serif",
            },
            "data": {
                "canId": "0x102",
                "startByte": 0,
                "length": 1,
                "endianness": "big",
                "signed": False,
                "scale": 1,
                "offset": 0,
                "precision": 0,
                "min": 0,
                "max": 140,
                "demoMin": 70,
                "demoMax": 122,
            },
            "alerts": [
                {
                    "id": "temp-high",
                    "label": "High Temp",
                    "operator": ">=",
                    "value": 110,
                    "severity": "warning",
                    "message": "Cooling check",
                    "color": "#f59e0b",
                }
            ],
        },
    ],
}


def ensure_config() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        ensure_config()
        self.config = normalize_config(self.load())
        self.path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")

    def load(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def get(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.config))

    def save(self, config: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.config = normalize_config(config)
            self.path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
            return self.get()


@dataclass
class CANFrame:
    can_id: int
    data: bytes
    timestamp: float


class CANManager:
    def __init__(self, store: ConfigStore):
        self.store = store
        self.lock = threading.Lock()
        self.latest_frames: dict[int, CANFrame] = {}
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def update_config(self) -> None:
        # Config is read on each loop iteration, so no explicit action is needed.
        return

    def _loop(self) -> None:
        can_socket: socket.socket | None = None
        last_mode: tuple[str, str] | None = None
        while self.running:
            config = self.store.get()
            can_cfg = config.get("settings", {}).get("can", {})
            mode = can_cfg.get("mode", "demo")
            channel = can_cfg.get("channel", "can0")
            mode_key = (mode, channel)

            if mode_key != last_mode and can_socket:
                can_socket.close()
                can_socket = None
            last_mode = mode_key

            if mode == "socketcan":
                if can_socket is None:
                    try:
                        can_socket = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
                        can_socket.bind((channel,))
                        can_socket.settimeout(0.5)
                    except OSError:
                        can_socket = None
                        self._simulate(config)
                        time.sleep(0.2)
                        continue
                try:
                    raw_frame = can_socket.recv(16)
                    can_id, data_length = struct.unpack("=IB3x", raw_frame[:8])
                    data = raw_frame[8 : 8 + data_length]
                    self._store_frame(can_id & socket.CAN_EFF_MASK, data)
                except TimeoutError:
                    continue
                except OSError:
                    can_socket = None
                    time.sleep(0.2)
            else:
                self._simulate(config)
                time.sleep(0.12)

    def _store_frame(self, can_id: int, data: bytes) -> None:
        with self.lock:
            self.latest_frames[can_id] = CANFrame(can_id=can_id, data=data, timestamp=time.time())

    def _simulate(self, config: dict[str, Any]) -> None:
        now = time.time()
        for index, widget in enumerate(config.get("widgets", [])):
            data_cfg = widget.get("data", {})
            can_id = parse_can_id(data_cfg.get("canId", "0x000"))
            length = max(1, min(8, int(data_cfg.get("length", 2))))
            demo_min = float(data_cfg.get("demoMin", data_cfg.get("min", 0)))
            demo_max = float(data_cfg.get("demoMax", data_cfg.get("max", 100)))
            phase = now * (0.8 + index * 0.17)
            normalized = (math.sin(phase) + 1) / 2
            jitter = random.uniform(-0.02, 0.02)
            value = demo_min + (demo_max - demo_min) * min(1, max(0, normalized + jitter))
            raw_value = encode_raw_value(value, data_cfg, length)
            self._store_frame(can_id, raw_value)

    def read_widget_value(self, widget: dict[str, Any]) -> dict[str, Any]:
        data_cfg = widget.get("data", {})
        can_id = parse_can_id(data_cfg.get("canId", "0x000"))
        with self.lock:
            frame = self.latest_frames.get(can_id)
        if frame is None:
            return {"value": None, "raw": None, "stale": True, "timestamp": None}
        raw_value = decode_raw_value(frame.data, data_cfg)
        scaled = raw_value * float(data_cfg.get("scale", 1)) + float(data_cfg.get("offset", 0))
        precision = int(data_cfg.get("precision", 0))
        value = round(scaled, precision)
        alert = evaluate_alerts(value, widget.get("alerts", []))
        return {
            "value": value,
            "raw": raw_value,
            "timestamp": frame.timestamp,
            "stale": (time.time() - frame.timestamp) > 2.0,
            "alert": alert,
        }


def parse_can_id(value: str | int) -> int:
    if isinstance(value, int):
        return value
    value = str(value).strip().lower()
    if value.startswith("0x"):
        return int(value, 16)
    return int(value)


def decode_raw_value(data: bytes, data_cfg: dict[str, Any]) -> int:
    start = max(0, int(data_cfg.get("startByte", 0)))
    length = max(1, min(8, int(data_cfg.get("length", 1))))
    chunk = data[start : start + length]
    if len(chunk) < length:
        chunk = chunk + bytes(length - len(chunk))
    byteorder = "little" if data_cfg.get("endianness") == "little" else "big"
    signed = bool(data_cfg.get("signed", False))
    return int.from_bytes(chunk, byteorder=byteorder, signed=signed)


def encode_raw_value(value: float, data_cfg: dict[str, Any], length: int) -> bytes:
    scale = float(data_cfg.get("scale", 1)) or 1.0
    offset = float(data_cfg.get("offset", 0))
    signed = bool(data_cfg.get("signed", False))
    byteorder = "little" if data_cfg.get("endianness") == "little" else "big"
    raw_value = int((value - offset) / scale)
    min_val = -(2 ** (length * 8 - 1)) if signed else 0
    max_val = (2 ** (length * 8 - (1 if signed else 0))) - 1
    raw_value = max(min_val, min(max_val, raw_value))
    return int(raw_value).to_bytes(length, byteorder=byteorder, signed=signed)


def evaluate_alerts(value: float | None, alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if value is None:
        return None
    for alert in alerts:
        threshold = float(alert.get("value", 0))
        operator = alert.get("operator", ">=")
        matched = {
            ">=": value >= threshold,
            "<=": value <= threshold,
            ">": value > threshold,
            "<": value < threshold,
            "==": value == threshold,
            "!=": value != threshold,
        }.get(operator, False)
        if matched:
            return alert
    return None


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _json_response(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._json_response(self.server.store.get())
            return
        if parsed.path == "/api/state":
            config = self.server.store.get()
            widgets = []
            for widget in config.get("widgets", []):
                widgets.append({"id": widget.get("id"), **self.server.can_manager.read_widget_value(widget)})
            self._json_response({"widgets": widgets, "serverTime": time.time()})
            return
        if parsed.path == "/api/status":
            config = self.server.store.get()
            self._json_response({"ok": True, "can": config.get("settings", {}).get("can", {})})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}

        if parsed.path == "/api/config":
            config = normalize_config(payload)
            saved = self.server.store.save(config)
            self.server.can_manager.update_config()
            self._json_response(saved)
            return

        if parsed.path == "/api/demo-reset":
            ensure_config()
            saved = self.server.store.save(copy.deepcopy(DEFAULT_CONFIG))
            self._json_response(saved)
            return

        self._json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_cls: type[DashboardHandler]):
        super().__init__(server_address, handler_cls)
        self.store = ConfigStore(CONFIG_PATH)
        self.can_manager = CANManager(self.store)


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(DEFAULT_CONFIG)
    normalized.update(config)
    normalized["settings"] = {**DEFAULT_CONFIG["settings"], **config.get("settings", {})}
    normalized["settings"]["theme"] = {
        **DEFAULT_CONFIG["settings"]["theme"],
        **config.get("settings", {}).get("theme", {}),
    }
    normalized["settings"]["can"] = {
        **DEFAULT_CONFIG["settings"]["can"],
        **config.get("settings", {}).get("can", {}),
    }
    normalized_widgets = []
    for index, widget in enumerate(config.get("widgets", [])):
        default_widget = json.loads(json.dumps(DEFAULT_CONFIG["widgets"][0]))
        default_widget["id"] = widget.get("id") or f"widget-{index}"
        default_widget["title"] = widget.get("title") or f"Widget {index + 1}"
        default_widget.update(widget)
        default_widget["position"] = {**default_widget["position"], **widget.get("position", {})}
        default_widget["style"] = {**default_widget["style"], **widget.get("style", {})}
        default_widget["data"] = {**default_widget["data"], **widget.get("data", {})}
        default_widget["alerts"] = widget.get("alerts", [])
        normalized_widgets.append(default_widget)
    normalized["widgets"] = normalized_widgets
    return normalized


def main() -> None:
    ensure_config()
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8765"))
    server = DashboardServer((host, port), DashboardHandler)
    print(f"Motorsport dashboard running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.can_manager.running = False
        server.server_close()


if __name__ == "__main__":
    main()
