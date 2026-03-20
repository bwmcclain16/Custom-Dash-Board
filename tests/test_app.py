import json
import threading
from urllib.request import Request, urlopen

from app.main import create_server


def start_test_server():
    server = create_server('127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_config_endpoint_returns_widgets():
    server, _ = start_test_server()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/config') as response:
            payload = json.loads(response.read().decode('utf-8'))
        assert payload['name']
        assert len(payload['widgets']) >= 1
    finally:
        server.shutdown()
        server.server_close()


def test_state_endpoint_contains_values_and_alerts():
    server, _ = start_test_server()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/state') as response:
            payload = json.loads(response.read().decode('utf-8'))
        assert 'values' in payload
        assert 'alerts' in payload
        assert 'source_status' in payload
    finally:
        server.shutdown()
        server.server_close()


def test_bus_endpoint_accepts_updates():
    server, _ = start_test_server()
    try:
        request = Request(
            f'http://127.0.0.1:{server.server_port}/api/bus',
            data=json.dumps({'interface': 'virtual', 'channel': 'demo', 'bitrate': 500000}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urlopen(request) as response:
            payload = json.loads(response.read().decode('utf-8'))
        assert payload['interface'] == 'virtual'
    finally:
        server.shutdown()
        server.server_close()
