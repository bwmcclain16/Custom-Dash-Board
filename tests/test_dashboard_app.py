import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.dashboard_app import (
    CanMonitor,
    ConfigStore,
    decode_signal,
    evaluate_alerts,
    normalize_alert_effect,
    normalize_config,
    normalize_operator,
    parse_can_id,
)


class DashboardAppTests(unittest.TestCase):
    def test_parse_can_id_supports_hex_and_decimal(self):
        self.assertEqual(parse_can_id("0x100"), 256)
        self.assertEqual(parse_can_id("512"), 512)

    def test_decode_signal_applies_endian_scale_and_offset(self):
        signal = {
            "startByte": 0,
            "byteLength": 2,
            "endian": "little",
            "signed": False,
            "scale": 0.5,
            "offset": 10,
        }
        self.assertEqual(decode_signal([100, 0], signal), 60)

    def test_decode_signal_supports_signed_big_endian(self):
        signal = {
            "startByte": 0,
            "byteLength": 2,
            "endian": "big",
            "signed": True,
            "scale": 1,
            "offset": 0,
        }
        self.assertEqual(decode_signal([0xFF, 0x9C], signal), -100)

    def test_evaluate_alerts_supports_word_operators_and_screen_effects(self):
        alerts = [
            {"name": "Warm", "operator": "greater_or_equal", "threshold": 90, "color": "orange", "effect": "screen_flash"},
            {"name": "Legacy", "operator": ">", "threshold": 110, "color": "red"},
        ]
        self.assertEqual(evaluate_alerts(95, alerts)["name"], "Warm")
        self.assertEqual(normalize_operator(">="), "greater_or_equal")
        self.assertEqual(normalize_alert_effect("flash"), "screen_flash")
        self.assertEqual(normalize_alert_effect("background_flash"), "background_flash")
        self.assertIsNone(evaluate_alerts(70, alerts))

    def test_normalize_config_fills_missing_defaults(self):
        config = normalize_config({"widgets": [{"name": "Oil Temp", "alerts": [{"threshold": 125, "effect": "solid"}]}]})
        widget = config["widgets"][0]
        self.assertEqual(widget["display"]["borderWidth"], 2)
        self.assertEqual(widget["display"]["imageOpacity"], 1.0)
        self.assertEqual(widget["display"]["layout"]["labelX"], 16)
        self.assertEqual(widget["display"]["gauge"]["tickCount"], 11)
        self.assertEqual(widget["alerts"][0]["operator"], "greater_or_equal")
        self.assertEqual(widget["alerts"][0]["effect"], "screen_solid")
        self.assertEqual(config["dashboard"]["width"], 1280)

    def test_normalize_config_adds_default_tire_sources(self):
        config = normalize_config({
            "widgets": [
                {
                    "name": "Tires",
                    "kind": "tire",
                    "source": {
                        "units": "°C",
                        "tires": {"lf": {"canId": "0x120"}},
                    },
                }
            ]
        })
        widget = config["widgets"][0]
        self.assertEqual(widget["source"]["tires"]["lf"]["canId"], "0x120")
        self.assertEqual(widget["source"]["tires"]["rf"]["canId"], "0x111")
        self.assertEqual(widget["source"]["tires"]["rr"]["canId"], "0x112")
        self.assertEqual(widget["source"]["tires"]["lr"]["canId"], "0x113")

    def test_decode_widget_supports_tire_widget_with_individual_can_ids(self):
        with TemporaryDirectory() as temp_dir:
            store = ConfigStore(Path(temp_dir) / "config.json")
            monitor = CanMonitor(store)
            widget = normalize_config({
                "widgets": [
                    {
                        "id": "widget-tires",
                        "name": "Tires",
                        "kind": "tire",
                        "source": {
                            "startByte": 0,
                            "byteLength": 1,
                            "units": "°C",
                            "tires": {
                                "lf": {"canId": "0x210"},
                                "rf": {"canId": "0x211"},
                                "rr": {"canId": "0x212"},
                                "lr": {"canId": "0x213"},
                            },
                        },
                        "display": {"decimalPlaces": 0},
                        "alerts": [{"threshold": 100, "operator": "greater_or_equal", "message": "HOT"}],
                    }
                ]
            })["widgets"][0]
            monitor.inject_frame(0x210, [88, 0, 0, 0, 0, 0, 0, 0], timestamp=1.0)
            monitor.inject_frame(0x211, [91, 0, 0, 0, 0, 0, 0, 0], timestamp=2.0)
            monitor.inject_frame(0x212, [104, 0, 0, 0, 0, 0, 0, 0], timestamp=3.0)
            monitor.inject_frame(0x213, [86, 0, 0, 0, 0, 0, 0, 0], timestamp=4.0)
            runtime = monitor.decode_widget(widget)
            self.assertEqual(runtime["tires"]["lf"]["formatted"], "88°C")
            self.assertEqual(runtime["tires"]["rf"]["label"], "RF")
            self.assertEqual(runtime["tires"]["rr"]["alert"]["message"], "HOT")
            self.assertEqual(runtime["alert"]["tireLabel"], "RR")
            self.assertAlmostEqual(runtime["summary"]["average"], 92.25)
            self.assertEqual(runtime["updatedAt"], 4.0)


if __name__ == "__main__":
    unittest.main()
