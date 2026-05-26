"""Application entry helpers."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from .ui.overlay_window import OverlayWindow


def _show_startup_notice() -> None:
    if not sys.platform.startswith("win"):
        QMessageBox.information(
            None,
            "平台提示",
            "当前平台不是 Windows。\n"
            "本项目目标运行环境为 Windows 10/11，\n"
            "热键与桌面截图在其他平台可能行为不同。",
        )


def main() -> int:
    app = QApplication(sys.argv)
    _show_startup_notice()

    window = OverlayWindow()
    window.show()
    return app.exec()

