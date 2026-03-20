from motorsport_dashboard.can_bus import evaluate_alert
from motorsport_dashboard.models import AlertRule, CanSignal, DashboardConfig, WidgetConfig


def test_can_signal_decode_with_scale_and_offset() -> None:
    signal = CanSignal(arbitration_id=0x200, start_byte=1, length_bytes=2, scale=0.5, offset=-10)
    data = bytes([0x00, 0x20, 0x03, 0, 0, 0, 0, 0])
    assert signal.decode(data) == 390.0


def test_dashboard_round_trip(tmp_path) -> None:
    config = DashboardConfig.default()
    path = tmp_path / "dashboard.json"
    config.save(path)
    loaded = DashboardConfig.load(path)
    assert loaded.title == config.title
    assert len(loaded.widgets) == 2
    assert loaded.widgets[0].alerts[0].label == "Shift"


def test_alert_evaluation_prefers_matching_rule() -> None:
    widget = WidgetConfig(alerts=[AlertRule(label="Hot", operator=">=", threshold=101)])
    result = evaluate_alert(
        105,
        widget.alerts,
        lambda: {
            "text": "",
            "text_color": widget.text_color,
            "background_color": widget.background_color,
            "border_color": widget.border_color,
        },
    )
    assert result["text"] == "Hot"
