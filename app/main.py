from __future__ import annotations

import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.canbus import CanMonitor
from app.config_store import ConfigStore
from app.models import AlertRule, DashboardConfig, DashboardState, WidgetConfig, dashboard_from_dict, to_dict

BASE_DIR = Path(__file__).resolve().parent
store = ConfigStore()
monitor = CanMonitor()
config = store.load()
monitor.start()


def extract_widget_value(widget: WidgetConfig):
    frame = monitor.get_frame(widget.source.can_id)
    if frame is None:
        return None
    source = widget.source
    segment = frame[source.start_byte : source.start_byte + source.length]
    if not segment:
        return None
    if source.data_type == "bool":
        return bool(segment[0] if source.bit_index is None else (segment[0] >> source.bit_index) & 1)
    if source.data_type == "hex":
        return segment.hex(" ")
    numeric = int.from_bytes(segment, byteorder=source.endianness, signed=source.signed)
    value = numeric * source.scale + source.offset
    return int(value) if source.data_type == "int" and widget.precision == 0 else round(value, widget.precision)


def matches(rule: AlertRule, value: float) -> bool:
    threshold = rule.threshold
    if rule.comparator == "between":
        return threshold is not None and rule.secondary_threshold is not None and threshold <= value <= rule.secondary_threshold
    if threshold is None:
        return False
    return {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
        "eq": value == threshold,
    }.get(rule.comparator, False)


def evaluate_alerts(widget: WidgetConfig, value) -> list[str]:
    if value is None or isinstance(value, str):
        return []
    messages: list[str] = []
    for rule in widget.alerts:
        if matches(rule, float(value)):
            messages.append(rule.message)
    if widget.kind == "status" and bool(value) and widget.warning_text:
        messages.append(widget.warning_text)
    return messages


def build_state() -> DashboardState:
    values: dict[str, float | int | bool | str | None] = {}
    alerts: dict[str, list[str]] = {}
    for widget in config.widgets:
        value = extract_widget_value(widget)
        values[widget.id] = value
        alerts[widget.id] = evaluate_alerts(widget, value)
    return DashboardState(config=config, values=values, alerts=alerts, source_status=monitor.status)


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(BASE_DIR / "templates" / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/config":
            self._respond_json(to_dict(config))
            return
        if parsed.path == "/api/state":
            self._respond_json(to_dict(build_state()))
            return
        if parsed.path.startswith("/static/"):
            self.path = parsed.path.replace("/static", "/static", 1)
            return super().do_GET()
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_json()
        global config
        if parsed.path == "/api/config":
            config = store.save(dashboard_from_dict(payload))
            self._respond_json(to_dict(config))
            return
        if parsed.path == "/api/bus":
            monitor.configure(
                payload.get("interface", "virtual"),
                payload.get("channel", "demo"),
                int(payload.get("bitrate", 500000)),
            )
            self._respond_json(payload)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _respond_json(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), partial(DashboardHandler, directory=str(BASE_DIR)))


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = create_server(host, port)
    print(f"Dashboard Studio running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        monitor.stop()


if __name__ == "__main__":
    run()
