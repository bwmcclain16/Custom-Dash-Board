import unittest

from src.dashboard_app import (
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
        self.assertIsNone(evaluate_alerts(70, alerts))

    def test_normalize_config_fills_missing_defaults(self):
        config = normalize_config({"widgets": [{"name": "Oil Temp", "alerts": [{"threshold": 125, "effect": "solid"}]}]})
        widget = config["widgets"][0]
        self.assertEqual(widget["display"]["borderWidth"], 2)
        self.assertEqual(widget["display"]["layout"]["labelX"], 16)
        self.assertEqual(widget["alerts"][0]["operator"], "greater_or_equal")
        self.assertEqual(widget["alerts"][0]["effect"], "screen_solid")
        self.assertEqual(config["dashboard"]["width"], 1280)


if __name__ == "__main__":
    unittest.main()
