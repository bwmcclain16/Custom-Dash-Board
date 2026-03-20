from __future__ import annotations

from collections.abc import Callable
from random import randint

try:
    from PySide6.QtCore import QObject, QTimer, Signal
except Exception:  # pragma: no cover - test environments may not have Qt
    class _DummySignal:
        def __init__(self, *args, **kwargs) -> None:
            self._subscribers = []

        def connect(self, callback) -> None:
            self._subscribers.append(callback)

        def emit(self, *args, **kwargs) -> None:
            for callback in list(self._subscribers):
                callback(*args, **kwargs)

    class Signal:  # type: ignore[override]
        def __init__(self, *args, **kwargs) -> None:
            self._name = None

        def __set_name__(self, owner, name) -> None:
            self._name = f"__signal_{name}"

        def __get__(self, instance, owner):
            if instance is None:
                return self
            signal = instance.__dict__.get(self._name)
            if signal is None:
                signal = _DummySignal()
                instance.__dict__[self._name] = signal
            return signal

    class QObject:
        def __init__(self, parent=None) -> None:
            self.parent = parent

    class QTimer:
        def __init__(self, parent=None) -> None:
            self.timeout = _DummySignal()

        def start(self, interval: int) -> None:
            return None

        def stop(self) -> None:
            return None

from .models import DashboardConfig

try:
    import can
except Exception:  # pragma: no cover - import environment dependent
    can = None


class CanBusManager(QObject):
    frame_received = Signal(int, bytes)
    status_changed = Signal(str)

    def __init__(self, config: DashboardConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._bus = None
        self._notifier = None
        self._sim_timer = QTimer(self)
        self._sim_timer.timeout.connect(self._emit_simulated_frames)

    def start(self) -> None:
        if can is None or self.config.can_interface == "virtual":
            self.status_changed.emit("Simulation mode enabled")
            self._sim_timer.start(150)
            return
        try:
            self._bus = can.Bus(
                interface=self.config.can_interface,
                channel=self.config.can_channel,
                bitrate=self.config.can_bitrate,
            )
            self._notifier = can.Notifier(self._bus, [self._handle_message])
            self.status_changed.emit(f"Connected to CAN {self.config.can_interface}:{self.config.can_channel}")
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.status_changed.emit(f"CAN connection failed, using simulation: {exc}")
            self._sim_timer.start(150)

    def stop(self) -> None:
        self._sim_timer.stop()
        if self._notifier is not None:
            self._notifier.stop()
        if self._bus is not None:
            self._bus.shutdown()
        self.status_changed.emit("CAN stopped")

    def _handle_message(self, message: object) -> None:
        arbitration_id = getattr(message, "arbitration_id", 0)
        data = bytes(getattr(message, "data", b""))
        self.frame_received.emit(arbitration_id, data)

    def _emit_simulated_frames(self) -> None:
        for widget in self.config.widgets:
            raw_max = max(1, int((widget.signal.max_value - widget.signal.offset) / max(widget.signal.scale, 0.0001)))
            raw_value = randint(0, raw_max)
            data = raw_value.to_bytes(widget.signal.length_bytes, byteorder=widget.signal.endian, signed=widget.signal.signed)
            payload = bytearray(8)
            payload[widget.signal.start_byte : widget.signal.start_byte + widget.signal.length_bytes] = data
            self.frame_received.emit(widget.signal.arbitration_id, bytes(payload))


def evaluate_alert(value: float, rules: list, fallback: Callable[[], dict[str, str]]) -> dict[str, str]:
    for rule in rules:
        if rule.matches(value):
            return {
                "text": rule.label,
                "text_color": rule.text_color,
                "background_color": rule.background_color,
                "border_color": rule.border_color,
            }
    return fallback()
