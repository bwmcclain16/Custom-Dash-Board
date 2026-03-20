from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AlertRule:
    id: str
    label: str = "Alert"
    comparator: str = "gt"
    threshold: float | None = None
    secondary_threshold: float | None = None
    color: str = "#ff4d4f"
    background_color: str = "rgba(255,77,79,0.2)"
    message: str = "Threshold reached"


@dataclass
class CanSource:
    can_id: str = "0x100"
    start_byte: int = 0
    length: int = 2
    endianness: str = "little"
    signed: bool = False
    scale: float = 1.0
    offset: float = 0.0
    data_type: str = "int"
    bit_index: int | None = None


@dataclass
class WidgetStyle:
    background_color: str = "#111827"
    text_color: str = "#f3f4f6"
    accent_color: str = "#38bdf8"
    border_color: str = "#334155"
    border_width: int = 2
    border_radius: int = 14
    background_image: str = ""
    font_family: str = "Inter, sans-serif"
    font_size: int = 18
    value_font_size: int = 34
    show_border: bool = True


@dataclass
class WidgetLayout:
    x: int = 24
    y: int = 24
    width: int = 240
    height: int = 160
    z_index: int = 1


@dataclass
class WidgetConfig:
    id: str
    title: str = "Widget"
    kind: str = "value"
    unit: str = ""
    description: str = ""
    source: CanSource = field(default_factory=CanSource)
    style: WidgetStyle = field(default_factory=WidgetStyle)
    layout: WidgetLayout = field(default_factory=WidgetLayout)
    precision: int = 1
    min_value: float = 0.0
    max_value: float = 100.0
    warning_text: str = ""
    alerts: list[AlertRule] = field(default_factory=list)


@dataclass
class DashboardTheme:
    background_color: str = "#020617"
    grid_color: str = "rgba(148,163,184,0.14)"
    panel_color: str = "#0f172a"
    text_color: str = "#e2e8f0"
    background_image: str = ""


@dataclass
class DashboardConfig:
    name: str = "Race Dashboard"
    width: int = 1280
    height: int = 720
    theme: DashboardTheme = field(default_factory=DashboardTheme)
    widgets: list[WidgetConfig] = field(default_factory=list)


@dataclass
class DashboardState:
    config: DashboardConfig
    values: dict[str, float | int | bool | str | None]
    alerts: dict[str, list[str]]
    source_status: str


def alert_rule_from_dict(data: dict[str, Any]) -> AlertRule:
    return AlertRule(**data)


def can_source_from_dict(data: dict[str, Any]) -> CanSource:
    return CanSource(**data)


def widget_style_from_dict(data: dict[str, Any]) -> WidgetStyle:
    return WidgetStyle(**data)


def widget_layout_from_dict(data: dict[str, Any]) -> WidgetLayout:
    return WidgetLayout(**data)


def widget_from_dict(data: dict[str, Any]) -> WidgetConfig:
    payload = dict(data)
    payload['source'] = can_source_from_dict(payload.get('source', {}))
    payload['style'] = widget_style_from_dict(payload.get('style', {}))
    payload['layout'] = widget_layout_from_dict(payload.get('layout', {}))
    payload['alerts'] = [alert_rule_from_dict(item) for item in payload.get('alerts', [])]
    return WidgetConfig(**payload)


def theme_from_dict(data: dict[str, Any]) -> DashboardTheme:
    return DashboardTheme(**data)


def dashboard_from_dict(data: dict[str, Any]) -> DashboardConfig:
    payload = dict(data)
    payload['theme'] = theme_from_dict(payload.get('theme', {}))
    payload['widgets'] = [widget_from_dict(item) for item in payload.get('widgets', [])]
    return DashboardConfig(**payload)


def to_dict(instance: Any) -> dict[str, Any]:
    return asdict(instance)
