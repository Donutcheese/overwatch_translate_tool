"""应用图标设置（窗口 + Windows 任务栏）。"""

from __future__ import annotations

import sys
import tkinter as tk

from ..core.paths import icon_ico_path


def apply_app_icon(window: tk.Misc) -> None:
    """为 Tk/CTk 窗口与 Windows 进程设置图标。"""
    ico_path = icon_ico_path()
    if not ico_path.is_file():
        return

    icon_file = str(ico_path.resolve())

    if sys.platform.startswith("win"):
        _set_windows_app_id()
        _set_windows_hwnd_icon(window, icon_file)

    try:
        window.iconbitmap(default=icon_file)
    except tk.TclError:
        pass


def _set_windows_app_id() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        app_id = "Donutcheese.OWColorFluentTranslator.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def _set_windows_hwnd_icon(window: tk.Misc, icon_file: str) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import win32api
        import win32con
        import win32gui

        window.update_idletasks()
        hwnd = int(window.winfo_id())
        try:
            parent = win32gui.GetParent(hwnd)
            if parent:
                hwnd = int(parent)
        except Exception:
            pass

        icon_handle = win32gui.LoadImage(
            None,
            icon_file,
            win32con.IMAGE_ICON,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
        )
        if not icon_handle:
            return

        win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, icon_handle)
        win32api.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, icon_handle)
    except Exception:
        pass
