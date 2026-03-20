from __future__ import annotations

import json
from pathlib import Path

from app.models import DashboardConfig, dashboard_from_dict, to_dict


class ConfigStore:
    def __init__(self, path: str = "dashboard-config.json") -> None:
        self.path = Path(path)

    def load(self) -> DashboardConfig:
        if not self.path.exists():
            return self.default()
        return dashboard_from_dict(json.loads(self.path.read_text()))

    def save(self, config: DashboardConfig) -> DashboardConfig:
        self.path.write_text(json.dumps(to_dict(config), indent=2))
        return config

    @staticmethod
    def default() -> DashboardConfig:
        return dashboard_from_dict(
            {
                "name": "Track Day Layout",
                "widgets": [
                    {
                        "id": "rpm",
                        "title": "RPM",
                        "kind": "gauge",
                        "unit": "rpm",
                        "max_value": 9000,
                        "source": {"can_id": "0x100", "start_byte": 0, "length": 2, "scale": 1},
                        "layout": {"x": 36, "y": 42, "width": 310, "height": 220, "z_index": 1},
                        "alerts": [
                            {
                                "id": "rpm-redline",
                                "label": "Redline",
                                "comparator": "gt",
                                "threshold": 7800,
                                "color": "#f97316",
                                "background_color": "rgba(249,115,22,0.25)",
                                "message": "Shift now"
                            }
                        ]
                    },
                    {
                        "id": "speed",
                        "title": "Speed",
                        "kind": "value",
                        "unit": "mph",
                        "source": {"can_id": "0x100", "start_byte": 2, "length": 2, "scale": 1},
                        "layout": {"x": 380, "y": 42, "width": 250, "height": 180, "z_index": 1}
                    },
                    {
                        "id": "coolant",
                        "title": "Coolant",
                        "kind": "bar",
                        "unit": "°C",
                        "max_value": 130,
                        "source": {"can_id": "0x101", "start_byte": 0, "length": 2, "scale": 1},
                        "layout": {"x": 36, "y": 292, "width": 300, "height": 160, "z_index": 1},
                        "alerts": [
                            {
                                "id": "coolant-hot",
                                "label": "Hot",
                                "comparator": "gt",
                                "threshold": 102,
                                "color": "#ef4444",
                                "background_color": "rgba(239,68,68,0.20)",
                                "message": "Coolant temp high"
                            }
                        ]
                    },
                    {
                        "id": "warning",
                        "title": "Engine Warning",
                        "kind": "status",
                        "source": {"can_id": "0x102", "start_byte": 0, "length": 1, "data_type": "bool"},
                        "warning_text": "Engine attention required",
                        "layout": {"x": 380, "y": 254, "width": 250, "height": 120, "z_index": 2}
                    }
                ]
            }
        )
