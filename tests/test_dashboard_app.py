import unittest

from src.dashboard_app import decode_signal, evaluate_alerts, parse_can_id


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

    def test_evaluate_alerts_returns_first_matching_alert(self):
        alerts = [
            {"name": "Warm", "operator": ">=", "threshold": 90, "color": "orange"},
            {"name": "Hot", "operator": ">=", "threshold": 110, "color": "red"},
        ]
        self.assertEqual(evaluate_alerts(95, alerts)["name"], "Warm")
        self.assertIsNone(evaluate_alerts(70, alerts))


if __name__ == "__main__":
    unittest.main()
