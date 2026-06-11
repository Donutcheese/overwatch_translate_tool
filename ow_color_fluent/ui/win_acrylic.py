"""Windows 窗口 Acrylic / Mica 毛玻璃（Win10/11，含 24H2/26H1）。"""

from __future__ import annotations

import ctypes
import sys

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004

# Win11 22H2+ — DwmSetWindowAttribute
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2  # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic（浮层推荐）
DWMSBT_TABBEDWINDOW = 4
DWMWCP_ROUND = 2

WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
ACCENT_ENABLE_HOSTBACKDROP = 5


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint32),
        ("AnimationId", ctypes.c_int),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(_ACCENT_POLICY)),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _dwm_set_int(hwnd: int, attr: int, value: int) -> bool:
    try:
        buf = ctypes.c_int(value)
        hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            attr,
            ctypes.byref(buf),
            ctypes.sizeof(buf),
        )
        return hr == 0
    except Exception:
        return False


def _set_window_composition(hwnd: int, accent: _ACCENT_POLICY) -> bool:
    try:
        set_attr = ctypes.windll.user32.SetWindowCompositionAttribute
    except Exception:
        return False
    data = _WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.Data = ctypes.pointer(accent)
    data.SizeOfData = ctypes.sizeof(accent)
    try:
        return bool(set_attr(hwnd, ctypes.byref(data)))
    except Exception:
        return False


def prepare_hwnd_for_dwm_blur(hwnd: int) -> None:
    """colorkey 透明 + WS_EX_LAYERED 会阻止 DWM 合成，启用毛玻璃前需清理。"""
    if hwnd <= 0:
        return
    try:
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style &= ~WS_EX_TRANSPARENT
        style &= ~WS_EX_LAYERED
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )
    except Exception:
        pass


def _disable_all_blur(hwnd: int) -> None:
    _dwm_set_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_NONE)
    accent = _ACCENT_POLICY()
    accent.AccentState = ACCENT_DISABLED
    _set_window_composition(hwnd, accent)


def _enable_win11_backdrop(hwnd: int) -> bool:
    """Win11 官方 DWM 通道（26H1 / 24H2 等）。"""
    _dwm_set_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    _dwm_set_int(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    for backdrop in (DWMSBT_TRANSIENTWINDOW, DWMSBT_MAINWINDOW, DWMSBT_TABBEDWINDOW):
        if _dwm_set_int(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, backdrop):
            return True
    return False


def _enable_legacy_acrylic(hwnd: int, tint_abgr: int) -> bool:
    """Win10 / 旧 Win11 回退通道。"""
    candidates = (
        (ACCENT_ENABLE_HOSTBACKDROP, 0, tint_abgr),
        (ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, tint_abgr),
        (ACCENT_ENABLE_BLURBEHIND, 0, 0),
    )
    for state, flags, color in candidates:
        accent = _ACCENT_POLICY()
        accent.AccentState = state
        accent.AccentFlags = flags
        accent.GradientColor = color
        accent.AnimationId = 0
        if _set_window_composition(hwnd, accent):
            return True
    return False


def set_acrylic_blur(hwnd: int, enabled: bool, tint_abgr: int = 0x99101826) -> bool:
    """启用/关闭毛玻璃。返回是否成功启用 DWM 效果。"""
    if not sys.platform.startswith("win") or hwnd <= 0:
        return False

    if not enabled:
        _disable_all_blur(hwnd)
        return False

    prepare_hwnd_for_dwm_blur(hwnd)
    if _enable_win11_backdrop(hwnd):
        return True
    return _enable_legacy_acrylic(hwnd, tint_abgr)
