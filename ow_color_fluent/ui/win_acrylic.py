"""Windows 窗口 Acrylic / Mica 毛玻璃（Win10/11）。"""

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


WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
ACCENT_ENABLE_HOSTBACKDROP = 5  # Win11 Mica 风格


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
    """colorkey 透明 + WS_EX_LAYERED 会阻止 DWM 毛玻璃，启用前需清理。"""
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


def set_acrylic_blur(hwnd: int, enabled: bool, tint_abgr: int = 0x99101826) -> None:
    """启用/关闭毛玻璃。Win11 优先 Mica，回退 Acrylic / Blur。"""
    if not sys.platform.startswith("win") or hwnd <= 0:
        return

    if not enabled:
        accent = _ACCENT_POLICY()
        accent.AccentState = ACCENT_DISABLED
        _set_window_composition(hwnd, accent)
        return

    prepare_hwnd_for_dwm_blur(hwnd)

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
            return
