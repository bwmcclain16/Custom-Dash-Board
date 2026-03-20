from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
from typing import Any, Literal
import uuid

WidgetType = Literal["digital", "bar", "indicator"]
Endian = Literal["little", "big"]


@dataclass(slots=True)
class AlertRule:
    label: str = "Warning"
    operator: Literal[">", ">=", "<", "<=", "==", "!="] = ">="
    threshold: float = 100.0
    text_color: str = "#ffffff"
    background_color: str = "#c62828"
    border_color: str = "#ffeb3b"
    enabled: bool = True

    def matches(self, value: float) -> bool:
        comparisons = {
            ">": value > self.threshold,
            ">=": value >= self.threshold,
            "<": value < self.threshold,
            "<=": value <= self.threshold,
            "==": value == self.threshold,
            "!=": value != self.threshold,
        }
        return self.enabled and comparisons[self.operator]


@dataclass(slots=True)
class CanSignal:
    arbitration_id: int = 0x100
    start_byte: int = 0
    length_bytes: int = 2
    signed: bool = False
    endian: Endian = "little"
    scale: float = 1.0
    offset: float = 0.0
    units: str = ""
    min_value: float = 0.0
    max_value: float = 100.0

    def decode(self, data: bytes) -> float:
        segment = data[self.start_byte : self.start_byte + self.length_bytes]
        if len(segment) < self.length_bytes:
            return 0.0
        raw = int.from_bytes(segment, byteorder=self.endian, signed=self.signed)
        return raw * self.scale + self.offset


@dataclass(slots=True)
class WidgetConfig:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "New Widget"
    widget_type: WidgetType = "digital"
    x: int = 80
    y: int = 80
    width: int = 220
    height: int = 120
    title: str = "Widget"
    show_title: bool = True
    value_prefix: str = ""
    value_suffix: str = ""
    decimals: int = 1
    font_family: str = "Arial"
    value_font_size: int = 28
    title_font_size: int = 12
    text_color: str = "#f5f5f5"
    background_color: str = "#1f2937"
    border_color: str = "#38bdf8"
    border_width: int = 2
    border_radius: int = 16
    background_image: str = ""
    warning_text: str = ""
    signal: CanSignal = field(default_factory=CanSignal)
    alerts: list[AlertRule] = field(default_factory=list)

    def display_value(self, value: float) -> str:
        return f"{self.value_prefix}{value:.{self.decimals}f}{self.value_suffix}"


@dataclass(slots=True)
class DashboardTheme:
    name: str = "Track Night"
    canvas_color: str = "#0f172a"
    grid_color: str = "#1e293b"
    background_image: str = ""
    snap_to_grid: bool = True
    grid_size: int = 20


@dataclass(slots=True)
class DashboardConfig:
    title: str = "Custom Motorsport Dashboard"
    theme: DashboardTheme = field(default_factory=DashboardTheme)
    widgets: list[WidgetConfig] = field(default_factory=list)
    can_interface: str = "virtual"
    can_channel: str = "dashboard"
    can_bitrate: int = 500000

    @classmethod
    def default(cls) -> "DashboardConfig":
        return cls(
            widgets=[
                WidgetConfig(
                    name="Engine RPM",
                    title="RPM",
                    widget_type="digital",
                    x=80,
                    y=80,
                    value_suffix=" rpm",
                    decimals=0,
                    signal=CanSignal(arbitration_id=0x101, start_byte=0, length_bytes=2, scale=1.0, max_value=9000),
                    alerts=[AlertRule(label="Shift", operator=">=", threshold=7800, background_color="#7f1d1d", border_color="#facc15")],
                ),
                WidgetConfig(
                    name="Coolant Temp",
                    title="Coolant",
                    widget_type="bar",
                    x=340,
                    y=80,
                    value_suffix=" °C",
                    decimals=1,
                    signal=CanSignal(arbitration_id=0x102, start_byte=0, length_bytes=2, scale=0.1, max_value=130),
                    alerts=[AlertRule(label="Hot", operator=">=", threshold=105, background_color="#991b1b", border_color="#fb923c")],
                ),
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DashboardConfig":
        theme = DashboardTheme(**payload.get("theme", {}))
        widgets: list[WidgetConfig] = []
        for item in payload.get("widgets", []):
            signal = CanSignal(**item.get("signal", {}))
            alerts = [AlertRule(**rule) for rule in item.get("alerts", [])]
            widget_data = {key: value for key, value in item.items() if key not in {"signal", "alerts"}}
            widgets.append(WidgetConfig(signal=signal, alerts=alerts, **widget_data))
        return cls(
            title=payload.get("title", "Custom Motorsport Dashboard"),
            theme=theme,
            widgets=widgets,
            can_interface=payload.get("can_interface", "virtual"),
            can_channel=payload.get("can_channel", "dashboard"),
            can_bitrate=payload.get("can_bitrate", 500000),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "DashboardConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
