from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass

try:
    import can  # type: ignore
except Exception:  # pragma: no cover
    can = None


@dataclass
class BusSettings:
    interface: str = "virtual"
    channel: str = "demo"
    bitrate: int = 500000


class CanMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames: dict[str, bytes] = {}
        self._status = "demo"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.settings = BusSettings()

    @property
    def status(self) -> str:
        return self._status

    def configure(self, interface: str, channel: str, bitrate: int) -> None:
        self.settings = BusSettings(interface=interface, channel=channel, bitrate=bitrate)
        self.restart()

    def restart(self) -> None:
        self.stop()
        self.start()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        if self.settings.interface == "virtual" or can is None:
            self._status = "demo"
            self._run_demo_loop()
            return

        try:
            bus = can.Bus(interface=self.settings.interface, channel=self.settings.channel, bitrate=self.settings.bitrate)
            self._status = f"live:{self.settings.interface}:{self.settings.channel}"
        except Exception as exc:  # pragma: no cover
            self._status = f"demo:fallback ({exc})"
            self._run_demo_loop()
            return

        while not self._stop_event.is_set():  # pragma: no cover
            msg = bus.recv(timeout=0.25)
            if msg is None:
                continue
            can_id = hex(msg.arbitration_id)
            with self._lock:
                self._frames[can_id.lower()] = bytes(msg.data)

    def _run_demo_loop(self) -> None:
        t = 0.0
        while not self._stop_event.is_set():
            rpm = int(2500 + 1800 * (1 + random.uniform(-0.08, 0.08)) * (0.5 + 0.5 * __import__("math").sin(t)))
            speed = int(90 + 70 * (0.5 + 0.5 * __import__("math").sin(t / 2)))
            coolant = int(82 + 25 * (0.5 + 0.5 * __import__("math").sin(t / 5)))
            fuel = int(10 + 90 * (0.5 + 0.5 * __import__("math").cos(t / 6)))
            warning = 1 if coolant > 100 else 0
            with self._lock:
                self._frames["0x100"] = rpm.to_bytes(2, "little", signed=False) + speed.to_bytes(2, "little", signed=False)
                self._frames["0x101"] = coolant.to_bytes(2, "little", signed=False) + fuel.to_bytes(2, "little", signed=False)
                self._frames["0x102"] = bytes([warning]) + b"\x00\x00\x00\x00\x00\x00\x00"
            time.sleep(0.15)
            t += 0.2

    def get_frame(self, can_id: str) -> bytes | None:
        with self._lock:
            return self._frames.get(can_id.lower())
