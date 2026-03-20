from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .models import DashboardConfig
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(DashboardConfig.default())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
