"""Application entry helpers."""

from __future__ import annotations

import sys
import tkinter.messagebox as messagebox

from .ui.overlay_window import OverlayWindow


def _show_startup_notice() -> None:
    if not sys.platform.startswith("win"):
        messagebox.showinfo(
            "平台提示",
            "当前平台不是 Windows。\n"
            "本项目目标运行环境为 Windows 10/11，\n"
            "热键与桌面截图在其他平台可能行为不同。",
        )


def main() -> int:
    if sys.platform.startswith("win"):
        from .ui.app_icon import _set_windows_app_id

        _set_windows_app_id()
    _show_startup_notice()
    window = OverlayWindow()
    window.mainloop()
    return 0
