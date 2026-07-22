"""Overlay window implementation (CustomTkinter)."""

from __future__ import annotations

import asyncio
import ctypes
import html
import os
import sys
import tkinter.font as tkfont
from concurrent.futures import Future
from typing import Any

import customtkinter as ctk

from ..core.config import (
    GLM_API_KEY,
    INPLACE_OVERLAY,
    PREFETCH_ENABLED,
    PREFETCH_INTERVAL_MS,
    TransResult,
)
from ..runtime.async_runtime import AsyncRuntime
from ..services.api_client import OWColorFluentApiClient, capture_region_to_base64
from .app_icon import apply_app_icon
from .win_acrylic import set_acrylic_blur

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover
    keyboard = None

try:
    import win32gui  # type: ignore
except Exception:  # pragma: no cover
    win32gui = None


HOTKEY_CAPTURE: str = os.getenv("HOTKEY_CAPTURE", "f8")
HOTKEY_TOGGLE_LOCK: str = os.getenv("HOTKEY_TOGGLE_LOCK", "f9")

TRANSPARENT_COLOR = "#000001"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

MIN_HEIGHT = 180
MIN_WIDTH = int(MIN_HEIGHT * 1.5)
BASE_REFERENCE_HEIGHT = MIN_HEIGHT

# 字体基准（1080p + 窗口高度 180px 时约为下列 px）
FONT_BASE_TITLE = 10
FONT_BASE_MODE = 8
FONT_BASE_REGION = 8
FONT_BASE_BODY = 9
FONT_BASE_BTN = 9
FONT_SCALE_MIN = 0.68
FONT_SCALE_MAX = 1.05

# F8 译文面板自动隐藏（毫秒，锁定模式下）
GLASS_AUTO_HIDE_MS = int(os.getenv("GLASS_AUTO_HIDE_MS", "12000"))
CAPTURE_HIDE_DELAY_MS = max(0, int(os.getenv("CAPTURE_HIDE_DELAY_MS", "35")))

# Fries Cup 视觉样式：https://fries-cup.com/zh
COLOR_YELLOW = "#F4C320"
COLOR_BLACK = "#2A2A2A"
COLOR_BLACK_DEEP = "#191919"
COLOR_WHITE = "#FFFFFF"
COLOR_PAPER = "#F7F5EF"
COLOR_YELLOW_PALE = "#FFF8D9"
COLOR_MUTED = "#B8B6AF"
COLOR_CARD_SETUP = COLOR_BLACK
COLOR_CARD_BORDER = COLOR_YELLOW
COLOR_TEXTBOX_SETUP = COLOR_BLACK_DEEP
COLOR_FRAME_PAD = 8
# F8 译文态毛玻璃失败时的回退底色（深色，保证译文可读）
COLOR_GLASS_FALLBACK = COLOR_BLACK_DEEP
# F8 译文态毛玻璃 tint（ABGR）：#191919，约 60% 不透明度。
GLASS_TINT_ABGR = int(os.getenv("GLASS_TINT_ABGR", "0x99191919"), 16)


def _enable_dpi_awareness() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class OverlayWindow(ctk.CTk):
    """主悬浮窗：可拖拽/缩放，支持锁定穿透与热键触发识别。"""

    def __init__(self) -> None:
        _enable_dpi_awareness()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        super().__init__()

        self._runtime = AsyncRuntime()
        self._api_client = OWColorFluentApiClient()
        self._locked = False
        self._busy = False
        self._capture_pending = False
        self._closing = False
        self._dragging = False
        self._resizing = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 0
        self._resize_start_h = 0
        self._tag_counter = 0
        self._resize_handle_size = 16
        self._font_scale = 1.0
        self._baseline_font_scale = 1.0
        self._last_scaled_h = 0
        self._visual_state = "setup"
        self._glass_hide_job: str | None = None
        self._glass_dismiss_bound = False
        self._acrylic_after_job: str | None = None
        self._prefetch_job: str | None = None
        self._inplace_labels: list[Any] = []
        self._inplace_layer: ctk.CTkFrame | None = None

        self.title("OW-Color-Fluent-Translator")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=TRANSPARENT_COLOR)
        self.attributes("-transparentcolor", TRANSPARENT_COLOR)
        apply_app_icon(self)

        self._min_w = MIN_WIDTH
        self._min_h = MIN_HEIGHT
        self._init_font_scale_from_screen()

        self._build_ui()
        self._connect_events()
        self._register_hotkeys()
        self._update_geometry_by_ratio()
        self._apply_ui_scale()
        self._apply_lock_mode(False)
        self._update_region_label()
        self._set_status("待命", COLOR_YELLOW)
        self.result_view.delete("1.0", "end")
        if not GLM_API_KEY.strip():
            self._insert_colored_text(
                "GLM_API_KEY 未配置：请在项目根目录创建 local_api_keys.py",
                color=COLOR_YELLOW,
            )
            self._insert_colored_text("示例：GLM_API_KEY = \"你的智谱Key\"", color=COLOR_MUTED)
        else:
            self._insert_colored_text("F8 识别 · F9 锁定后游戏中透明", color=COLOR_MUTED)

        # 后台预热 DeepSeek 指令前缀缓存，降低首次翻译 TTFT
        self._runtime.submit(self._api_client.warm_translation_prefix())

    def _get_screen_size(self) -> tuple[int, int]:
        if sys.platform.startswith("win"):
            try:
                width = int(ctypes.windll.user32.GetSystemMetrics(0))
                height = int(ctypes.windll.user32.GetSystemMetrics(1))
                if width > 0 and height > 0:
                    return width, height
            except Exception:
                pass
        self.update_idletasks()
        return int(self.winfo_screenwidth()), int(self.winfo_screenheight())

    def _update_geometry_by_ratio(self) -> None:
        screen_w, screen_h = self._get_screen_size()
        height = max(MIN_HEIGHT, int(screen_h / 6))
        width = max(MIN_WIDTH, int(height * 1.5))
        x = 20
        y = screen_h - height - 20
        self._set_font_scale_from_height(height)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self._capture_baseline_font_scale(height)
        self.update_idletasks()

    def _init_font_scale_from_screen(self) -> None:
        _, screen_h = self._get_screen_size()
        height = max(MIN_HEIGHT, int(screen_h / 6))
        self._capture_baseline_font_scale(height)

    def _set_font_scale_from_height(self, height: int) -> None:
        ratio = height / BASE_REFERENCE_HEIGHT
        self._font_scale = max(
            FONT_SCALE_MIN,
            min(FONT_SCALE_MAX, ratio),
        )
        self._resize_handle_size = max(12, int(height * 0.07))
        self._last_scaled_h = height

    def _capture_baseline_font_scale(self, height: int) -> None:
        """记录启动时屏幕比例字号；手动拉大窗口不再放大字体。"""
        self._set_font_scale_from_height(height)
        self._baseline_font_scale = self._font_scale

    def _font_size(self, base: int) -> int:
        return max(8, int(round(base * self._font_scale)))

    def _scaled_px(self, base: int) -> int:
        return max(1, int(round(base * self._font_scale)))

    def _refresh_font_scale_from_window(self) -> None:
        height = max(MIN_HEIGHT, int(self.winfo_height()))
        if abs(height - self._last_scaled_h) < 2:
            return
        ratio = height / BASE_REFERENCE_HEIGHT
        self._font_scale = max(
            FONT_SCALE_MIN,
            min(self._baseline_font_scale, ratio),
        )
        self._resize_handle_size = max(12, int(height * 0.07))
        self._last_scaled_h = height
        self._apply_ui_scale()

    def _scaled_font(self, base_size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(
            family="Segoe UI",
            size=self._font_size(base_size),
            weight=weight,
        )

    def _textbox_tag_font(self, base_size: int, weight: str = "normal") -> tkfont.Font:
        """CTkTextbox 内部 tkinter Text 的 tag 仍使用 tkinter.font.Font。"""
        return tkfont.Font(
            family="Segoe UI",
            size=self._font_size(base_size),
            weight=weight,
        )

    def _apply_ui_scale(self) -> None:
        dot_w = self._scaled_px(10)
        btn_w = self._scaled_px(72)
        btn_h = self._scaled_px(24)
        close_sz = self._scaled_px(24)

        self.dot_status.configure(width=dot_w, font=self._scaled_font(FONT_BASE_TITLE))
        self.title_label.configure(font=self._scaled_font(FONT_BASE_TITLE, "bold"))
        self.mode_label.configure(font=self._scaled_font(FONT_BASE_MODE))
        self.capture_btn.configure(
            width=btn_w,
            height=btn_h,
            font=self._scaled_font(FONT_BASE_BTN),
        )
        self.lock_btn.configure(
            width=btn_w,
            height=btn_h,
            font=self._scaled_font(FONT_BASE_BTN),
        )
        self.close_btn.configure(
            width=close_sz,
            height=close_sz,
            font=self._scaled_font(FONT_BASE_TITLE, "bold"),
        )
        self.region_label.configure(font=self._scaled_font(FONT_BASE_REGION))
        self.result_view.configure(font=self._scaled_font(FONT_BASE_BODY))
        self.resize_tip.configure(
            width=self._resize_handle_size,
            height=self._resize_handle_size,
            font=self._scaled_font(FONT_BASE_REGION),
        )

    def _maybe_apply_ui_scale(self) -> None:
        if self._visual_state == "hidden":
            return
        self._refresh_font_scale_from_window()

    def _build_ui(self) -> None:
        self.card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD_SETUP,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_CARD_BORDER,
        )
        self.card.pack(fill="both", expand=True, padx=8, pady=8)
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkFrame(self.card, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        self.header.grid_columnconfigure(1, weight=1)

        self.dot_status = ctk.CTkLabel(
            self.header,
            text="●",
            width=self._scaled_px(10),
            font=self._scaled_font(FONT_BASE_TITLE),
            text_color=COLOR_YELLOW,
        )
        self.dot_status.grid(row=0, column=0, padx=(0, 4))

        self.title_label = ctk.CTkLabel(
            self.header,
            text="OW Translator",
            font=self._scaled_font(FONT_BASE_TITLE, "bold"),
            text_color=COLOR_WHITE,
            anchor="w",
        )
        self.title_label.grid(row=0, column=1, sticky="ew")

        self.header_actions = ctk.CTkFrame(self.header, fg_color="transparent")
        self.header_actions.grid(row=0, column=2, sticky="e")

        self.mode_label = ctk.CTkLabel(
            self.header_actions,
            text="编辑模式",
            font=self._scaled_font(FONT_BASE_MODE),
            text_color=COLOR_YELLOW,
        )
        self.mode_label.pack(side="left", padx=(0, 6))

        self.capture_btn = ctk.CTkButton(
            self.header_actions,
            text=f"识别({HOTKEY_CAPTURE.upper()})",
            width=self._scaled_px(72),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_BTN),
            fg_color=COLOR_YELLOW,
            hover_color="#D9AA00",
            text_color=COLOR_BLACK,
            command=self.trigger_capture,
        )
        self.capture_btn.pack(side="left", padx=(0, 4))

        self.lock_btn = ctk.CTkButton(
            self.header_actions,
            text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})",
            width=self._scaled_px(72),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_BTN),
            fg_color=COLOR_BLACK_DEEP,
            hover_color=COLOR_BLACK,
            border_width=1,
            border_color=COLOR_YELLOW,
            text_color=COLOR_WHITE,
            command=self.toggle_lock_mode,
        )
        self.lock_btn.pack(side="left", padx=(0, 4))

        self.close_btn = ctk.CTkButton(
            self.header_actions,
            text="×",
            width=self._scaled_px(24),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_TITLE, "bold"),
            fg_color=COLOR_BLACK_DEEP,
            hover_color=COLOR_YELLOW,
            border_width=1,
            border_color=COLOR_YELLOW,
            text_color=COLOR_WHITE,
            command=self._on_close,
        )
        self.close_btn.pack(side="left")

        self.region_label = ctk.CTkLabel(
            self.card,
            text="",
            font=self._scaled_font(FONT_BASE_REGION),
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.region_label.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))

        self.result_view = ctk.CTkTextbox(
            self.card,
            font=self._scaled_font(FONT_BASE_BODY),
            fg_color=COLOR_TEXTBOX_SETUP,
            border_color=COLOR_YELLOW,
            border_width=1,
            text_color=COLOR_PAPER,
            wrap="word",
            activate_scrollbars=True,
        )
        self.result_view.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))

        # 原位覆盖层：与 result_view 同格，按 bbox 放置译文
        self._inplace_layer = ctk.CTkFrame(self.card, fg_color="transparent")
        self._inplace_layer.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))
        self._inplace_layer.lower(self.result_view)

        self.footer = ctk.CTkFrame(self.card, fg_color="transparent", height=self._scaled_px(18))
        self.footer.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 2))
        self.footer.grid_columnconfigure(0, weight=1)

        self.resize_tip = ctk.CTkLabel(
            self.footer,
            text="◢",
            font=self._scaled_font(FONT_BASE_REGION),
            text_color=COLOR_YELLOW,
            width=self._resize_handle_size,
            height=self._resize_handle_size,
        )
        self.resize_tip.grid(row=0, column=1, sticky="se", padx=(0, 2))

        drag_widgets = (
            self.header,
            self.dot_status,
            self.title_label,
            self.mode_label,
            self.region_label,
        )
        for widget in drag_widgets:
            widget.bind("<Button-1>", self._on_drag_start, add="+")
            widget.bind("<B1-Motion>", self._on_drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", self._on_drag_release, add="+")

        self.resize_tip.bind("<Button-1>", self._on_resize_start)
        self.resize_tip.bind("<B1-Motion>", self._on_resize_motion)
        self.resize_tip.bind("<ButtonRelease-1>", self._on_resize_release)

    def _connect_events(self) -> None:
        self.bind("<Configure>", self._on_configure)

    def _register_hotkeys(self) -> None:
        if keyboard is None:
            self._append_message("热键库不可用：将仅支持按钮触发。", COLOR_YELLOW)
            return
        try:
            keyboard.add_hotkey(
                HOTKEY_CAPTURE,
                lambda: self.after(0, self.trigger_capture),
                suppress=False,
            )
            keyboard.add_hotkey(
                HOTKEY_TOGGLE_LOCK,
                lambda: self.after(0, self.toggle_lock_mode),
                suppress=False,
            )
        except Exception as exc:
            self._append_message(f"热键注册失败：{exc}", COLOR_YELLOW)

    def _get_hwnd(self) -> int:
        wid = int(self.winfo_id())
        if win32gui is not None:
            try:
                parent = win32gui.GetParent(wid)
                if parent:
                    return int(parent)
            except Exception:
                pass
        return wid

    def _refresh_window_style(self, hwnd: int) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
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

    def _set_click_through(self, enabled: bool) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            hwnd = self._get_hwnd()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED
            if enabled:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self._refresh_window_style(hwnd)
        except Exception:
            pass

    def _cancel_glass_hide(self) -> None:
        if self._glass_hide_job:
            try:
                self.after_cancel(self._glass_hide_job)
            except Exception:
                pass
            self._glass_hide_job = None

    def _schedule_glass_hide(self) -> None:
        self._cancel_glass_hide()
        if self._locked and GLASS_AUTO_HIDE_MS > 0:
            self._glass_hide_job = self.after(GLASS_AUTO_HIDE_MS, self._hide_glass_panel)

    def _hide_glass_panel(self) -> None:
        self._glass_hide_job = None
        if self._locked and self._visual_state == "glass":
            self._return_to_locked_hidden()

    def _set_root_colorkey(self, enabled: bool) -> None:
        """启用/关闭 colorkey 穿透底色。"""
        if enabled:
            self.configure(fg_color=TRANSPARENT_COLOR)
            self.attributes("-transparentcolor", TRANSPARENT_COLOR)
            self._restore_layered_for_colorkey()
        else:
            try:
                self.attributes("-transparentcolor", "")
            except Exception:
                pass

    def _restore_layered_for_colorkey(self) -> None:
        """DWM 毛玻璃会移除分层窗口属性，切回 colorkey 前需恢复。"""
        if not sys.platform.startswith("win"):
            return
        try:
            hwnd = self._get_hwnd()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self._refresh_window_style(hwnd)
        except Exception:
            pass

    def _bind_glass_dismiss_events(self) -> None:
        if self._glass_dismiss_bound:
            return
        for widget in (self, self.card, self.result_view):
            widget.bind("<Escape>", self._return_to_locked_hidden, add="+")
            widget.bind("<Button-1>", self._return_to_locked_hidden, add="+")
            widget.bind("<Button-3>", self._return_to_locked_hidden, add="+")
        self._glass_dismiss_bound = True

    def _unbind_glass_dismiss_events(self) -> None:
        if not self._glass_dismiss_bound:
            return
        for widget in (self, self.card, self.result_view):
            for seq in ("<Escape>", "<Button-1>", "<Button-3>"):
                widget.unbind(seq)
        self._glass_dismiss_bound = False

    def _return_to_locked_hidden(self, _event: Any = None) -> str:
        """F8 译文态回到 F9 完全透明锁定态。"""
        if not self._locked or self._visual_state != "glass":
            return "break"
        self.result_view.delete("1.0", "end")
        self._set_visual_state("hidden")
        return "break"

    def _apply_acrylic(self, enabled: bool) -> None:
        if not sys.platform.startswith("win"):
            return
        # 取消上一次挂起的应用：避免 glass->setup 快速切换时，
        # 旧的 enabled=True 回调晚于 enabled=False 触发，导致毛玻璃残留。
        if self._acrylic_after_job:
            try:
                self.after_cancel(self._acrylic_after_job)
            except Exception:
                pass
            self._acrylic_after_job = None

        def _run() -> None:
            self._acrylic_after_job = None
            if self._closing:
                return
            self.update_idletasks()
            set_acrylic_blur(self._get_hwnd(), enabled, GLASS_TINT_ABGR)

        self._acrylic_after_job = self.after(50, _run)

    def _show_setup_widgets(self) -> None:
        self.card.grid_rowconfigure(0, weight=0)
        self.card.grid_rowconfigure(2, weight=1)
        self.header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        self.region_label.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))
        self.result_view.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))
        if self._inplace_layer is not None:
            self._inplace_layer.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))
            self._inplace_layer.lower(self.result_view)
        if not self._locked:
            self.footer.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 2))

    def _hide_setup_widgets(self) -> None:
        self.header.grid_remove()
        self.region_label.grid_remove()
        self.footer.grid_remove()

    def _set_visual_state(self, state: str) -> None:
        """setup=编辑对齐 | hidden=F9 完全透明 | glass=F8 毛玻璃+译文。"""
        self._visual_state = state
        self._cancel_glass_hide()
        self._unbind_glass_dismiss_events()
        self._apply_acrylic(False)

        if state == "hidden":
            self._set_root_colorkey(True)
            self.card.pack_configure(padx=0, pady=0)
            self.card.configure(
                fg_color=TRANSPARENT_COLOR,
                border_width=0,
                border_color=TRANSPARENT_COLOR,
            )
            self.result_view.configure(
                fg_color=TRANSPARENT_COLOR,
                border_width=0,
                border_color=TRANSPARENT_COLOR,
            )
            self._hide_setup_widgets()
            self.result_view.grid_remove()
            if self._locked:
                self._set_click_through(True)
            else:
                self._set_click_through(False)
            return

        if state == "setup":
            self._set_root_colorkey(True)
            self.card.pack_configure(padx=COLOR_FRAME_PAD, pady=COLOR_FRAME_PAD)
            self.card.configure(
                fg_color=COLOR_CARD_SETUP,
                border_width=1,
                border_color=COLOR_CARD_BORDER,
            )
            self.result_view.configure(
                fg_color=COLOR_TEXTBOX_SETUP,
                border_width=1,
                border_color=COLOR_YELLOW,
            )
            self._show_list_view()
            self._show_setup_widgets()
            self._set_click_through(False)
            self._refresh_font_scale_from_window()
            return

        if state == "glass":
            # F8 译文态：启用 DWM 毛玻璃，让译文浮在模糊背景上，提升可读性。
            # colorkey 透明依赖 WS_EX_LAYERED，会阻止 DWM 合成毛玻璃，故关闭 colorkey。
            self._set_root_colorkey(False)
            # acrylic 失败时的回退底色（深色，保证译文可读）；acrylic 成功时被毛玻璃覆盖。
            self.configure(fg_color=COLOR_GLASS_FALLBACK)
            self.card.pack_configure(padx=COLOR_FRAME_PAD, pady=COLOR_FRAME_PAD)
            self.card.configure(
                fg_color="transparent",
                border_width=1,
                border_color=COLOR_CARD_BORDER,
            )
            self.result_view.configure(
                fg_color="transparent",
                border_width=0,
                border_color="transparent",
            )
            self._hide_setup_widgets()
            self.result_view.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            if self._inplace_layer is not None:
                self._inplace_layer.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
                self._inplace_layer.lower(self.result_view)
            self.card.grid_rowconfigure(0, weight=1)
            self._set_click_through(False)
            self._bind_glass_dismiss_events()
            self._refresh_font_scale_from_window()
            self._apply_acrylic(True)  # 启用毛玻璃（Win11 DWM Acrylic / Mica）
            self._schedule_glass_hide()

    def trigger_capture(self) -> None:
        if self._busy:
            self._capture_pending = True
            self._set_status("排队中", COLOR_YELLOW)
            return
        region = self._current_capture_region()
        if region["width"] < 80 or region["height"] < 60:
            if self._locked:
                self._set_visual_state("glass")
            self._append_message("截图区域过小，请扩大窗口。", COLOR_YELLOW)
            return

        self._busy = True
        self._capture_pending = False
        self._set_status("识别中", COLOR_YELLOW)

        if self._locked:
            self._set_visual_state("hidden")
            self._launch_pipeline(region, restore_after_capture=False)
        else:
            self._set_visual_state("setup")
            self.withdraw()
            self.after(
                CAPTURE_HIDE_DELAY_MS,
                lambda: self._launch_pipeline(region, restore_after_capture=True),
            )

    def _restore_after_capture(self) -> None:
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        if self._locked:
            self._set_visual_state("glass")
        else:
            self._set_visual_state("setup")

    def _show_capture_progress(self, restore_window: bool) -> None:
        if self._closing:
            return
        if restore_window:
            self._restore_after_capture()
        elif self._locked:
            self._set_visual_state("glass")
        self.result_view.delete("1.0", "end")
        self._insert_colored_text("识别中...", color=COLOR_YELLOW, newline=False)

    def _launch_pipeline(
        self, region: dict[str, int], *, restore_after_capture: bool
    ) -> None:
        future = self._runtime.submit(
            self._pipeline(region, restore_after_capture=restore_after_capture)
        )
        future.add_done_callback(self._on_pipeline_future_done)

    def _on_pipeline_future_done(self, future: Future) -> None:
        try:
            payload = future.result()
            self.after(0, self._handle_pipeline_done, payload, "")
        except Exception as exc:
            self.after(0, self._handle_pipeline_done, None, str(exc))

    async def _pipeline(
        self, region: dict[str, int], *, restore_after_capture: bool
    ) -> dict[str, Any]:
        capture_data = await asyncio.to_thread(capture_region_to_base64, region)
        self.after(0, self._show_capture_progress, restore_after_capture)

        # 优先复用锁定态后台预取的新鲜 OCR，跳过一次网络往返
        ocr_results = self._api_client.take_prefetch_ocr_if_fresh(max_age_sec=1.2)
        if ocr_results is None:
            ocr_results = await self._api_client.process_multi_channel_ocr(capture_data)
        else:
            # 预取命中时仍异步刷新下一次预取指纹
            self._api_client.remember_prefetch_ocr(ocr_results)

        trans_results = await self._api_client.translate_ocr_results(ocr_results)
        return {"ocr": ocr_results, "trans": trans_results}

    async def _prefetch_ocr_once(self, region: dict[str, int]) -> None:
        capture_data = await asyncio.to_thread(capture_region_to_base64, region)
        ocr_results = await self._api_client.process_multi_channel_ocr(capture_data)
        self._api_client.remember_prefetch_ocr(ocr_results)
        # 预翻译：词典/记忆命中可提前写入，F8 时几乎瞬时
        await self._api_client.translate_ocr_results(ocr_results)

    def _schedule_prefetch(self) -> None:
        self._cancel_prefetch()
        if not PREFETCH_ENABLED or not self._locked or self._closing:
            return
        self._prefetch_job = self.after(PREFETCH_INTERVAL_MS, self._run_prefetch_tick)

    def _cancel_prefetch(self) -> None:
        if self._prefetch_job is not None:
            try:
                self.after_cancel(self._prefetch_job)
            except Exception:
                pass
            self._prefetch_job = None

    def _run_prefetch_tick(self) -> None:
        self._prefetch_job = None
        if not PREFETCH_ENABLED or not self._locked or self._closing or self._busy:
            self._schedule_prefetch()
            return
        region = self._current_capture_region()
        future = self._runtime.submit(self._prefetch_ocr_once(region))

        def _done(fut: Future) -> None:
            try:
                fut.result()
            except Exception:
                pass
            if not self._closing:
                self.after(0, self._schedule_prefetch)

        future.add_done_callback(_done)

    def _clear_inplace_labels(self) -> None:
        for label in self._inplace_labels:
            try:
                label.destroy()
            except Exception:
                pass
        self._inplace_labels.clear()

    def _show_list_view(self) -> None:
        self._clear_inplace_labels()
        if self._inplace_layer is not None:
            self._inplace_layer.grid_remove()
        self.result_view.grid()

    def _render_inplace_overlay(self, results: list[TransResult]) -> bool:
        """按 bbox 原位覆盖；成功返回 True，否则回退列表渲染。"""
        if not INPLACE_OVERLAY or self._inplace_layer is None:
            return False
        placed = [item for item in results if item.bbox is not None and item.translated.strip()]
        if not placed:
            return False

        self.result_view.grid_remove()
        self._inplace_layer.grid()
        self._clear_inplace_labels()
        self.update_idletasks()
        layer_w = max(1, int(self._inplace_layer.winfo_width()))
        layer_h = max(1, int(self._inplace_layer.winfo_height()))

        for item in placed:
            assert item.bbox is not None
            x0, y0, x1, y1 = item.bbox
            px = int(x0 * layer_w)
            py = int(y0 * layer_h)
            pw = max(self._scaled_px(48), int((x1 - x0) * layer_w))
            ph = max(self._scaled_px(16), int((y1 - y0) * layer_h))
            color = item.color_tag.hex_color if item.color_tag else "#E2E8F0"
            text = html.unescape(item.translated.strip())
            # 半透明底条盖住原文位置，配合窗口毛玻璃形成“模糊原语 + 中文覆盖”
            label = ctk.CTkLabel(
                self._inplace_layer,
                text=text,
                font=self._scaled_font(FONT_BASE_BODY, "bold"),
                text_color=color,
                fg_color="#101826",
                corner_radius=4,
                anchor="w",
                justify="left",
            )
            label.place(x=px, y=py, width=pw, height=ph)
            self._inplace_labels.append(label)
        return True

    def _handle_pipeline_done(self, payload: object, error: str) -> None:
        self._busy = False
        if self._locked:
            self._set_visual_state("glass")
        elif error or not isinstance(payload, dict):
            self._set_visual_state("setup")

        if error:
            self._set_status("失败", COLOR_YELLOW)
            self._append_message(f"识别失败：{error}", COLOR_YELLOW)
            self._run_pending_capture_if_needed()
            return
        if not isinstance(payload, dict):
            self._set_status("失败", COLOR_YELLOW)
            self._append_message("识别失败：返回结果异常。", COLOR_YELLOW)
            self._run_pending_capture_if_needed()
            return

        trans_results = payload.get("trans", [])
        ocr_results = payload.get("ocr", [])

        if trans_results:
            self.update_translation_list(trans_results)
            self._set_status("完成", COLOR_YELLOW)
        else:
            self._set_status("无结果", COLOR_YELLOW)
            self._render_ocr_fallback(ocr_results)

        if self._locked:
            self._schedule_glass_hide()
        else:
            self._set_visual_state("setup")

        self._run_pending_capture_if_needed()

    def _run_pending_capture_if_needed(self) -> None:
        if self._capture_pending and not self._closing:
            self._capture_pending = False
            self.after(40, self.trigger_capture)

    def _insert_colored_text(
        self,
        text: str,
        color: str = COLOR_PAPER,
        bold: bool = False,
        newline: bool = True,
    ) -> None:
        self._tag_counter += 1
        tag_name = f"color_tag_{self._tag_counter}"
        weight = "bold" if bold else "normal"
        font = self._textbox_tag_font(FONT_BASE_BODY, weight)
        self.result_view.tag_config(tag_name, foreground=color)
        try:
            self.result_view._textbox.tag_config(tag_name, foreground=color, font=font)
        except Exception:
            pass
        content = text + ("\n" if newline else "")
        self.result_view.insert("end", content, tag_name)
        self.result_view.see("end")

    def update_translation_list(self, results: list[TransResult]) -> None:
        if self._render_inplace_overlay(results):
            return
        self._show_list_view()
        self.result_view.delete("1.0", "end")
        for item in results:
            color = COLOR_PAPER
            label = "Unknown"
            if item.color_tag is not None:
                color = item.color_tag.hex_color
                label = item.color_tag.label
            text = html.unescape(item.translated.strip() or "(空)")
            self._insert_colored_text(f"[{label}] ", color=color, bold=True, newline=False)
            self._insert_colored_text(text, color=color, bold=False, newline=True)

    def _render_ocr_fallback(self, ocr_results: list[Any]) -> None:
        self._show_list_view()
        self.result_view.delete("1.0", "end")
        if not ocr_results:
            self._insert_colored_text("无可用 OCR 结果。")
            return

        messages: list[str] = []
        for item in ocr_results:
            msg = getattr(item, "error_msg", None) or "无文本输出"
            messages.append(str(msg))

        unique = list(dict.fromkeys(messages))
        if len(unique) == 1:
            self._insert_colored_text(unique[0], color=COLOR_YELLOW)
            if "GLM_API_KEY" in unique[0]:
                self._insert_colored_text(
                    "编辑 local_api_keys.py 后重启程序。",
                    color=COLOR_MUTED,
                )
            return

        for item in ocr_results:
            label = getattr(getattr(item, "color_tag", None), "label", "Unknown")
            msg = getattr(item, "error_msg", None) or "无文本输出"
            self._insert_colored_text(f"[{label}] {msg}", newline=True)

    def toggle_lock_mode(self) -> None:
        self._apply_lock_mode(not self._locked)

    def _apply_lock_mode(self, locked: bool) -> None:
        self._locked = locked
        if locked:
            self.mode_label.configure(text="锁定穿透")
            self.lock_btn.configure(text=f"解锁({HOTKEY_TOGGLE_LOCK.upper()})")
            self._set_visual_state("hidden")
            self._schedule_prefetch()
        else:
            self.mode_label.configure(text="编辑模式")
            self.lock_btn.configure(text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})")
            self._cancel_prefetch()
            self._show_list_view()
            self._set_visual_state("setup")
        self._update_region_label()

    def _on_drag_start(self, event: Any) -> None:
        if self._locked:
            return
        self._dragging = True
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event: Any) -> None:
        if self._locked or not self._dragging:
            return
        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self.geometry(f"+{x}+{y}")

    def _on_drag_release(self, _event: Any) -> None:
        self._dragging = False

    def _on_resize_start(self, event: Any) -> None:
        if self._locked:
            return
        self._resizing = True
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    def _on_resize_motion(self, event: Any) -> None:
        if self._locked or not self._resizing:
            return
        delta_x = event.x_root - self._resize_start_x
        delta_y = event.y_root - self._resize_start_y
        new_w = max(self._min_w, self._resize_start_w + delta_x)
        new_h = max(self._min_h, self._resize_start_h + delta_y)
        self.geometry(f"{new_w}x{new_h}")
        self._maybe_apply_ui_scale()

    def _on_resize_release(self, _event: Any) -> None:
        self._resizing = False
        self._maybe_apply_ui_scale()

    def _on_configure(self, event: Any) -> None:
        if event.widget is self:
            self._maybe_apply_ui_scale()
        self._update_region_label()

    def _current_capture_region(self) -> dict[str, int]:
        self.update_idletasks()
        return {
            "left": max(0, int(self.winfo_rootx())),
            "top": max(0, int(self.winfo_rooty())),
            "width": max(1, int(self.winfo_width())),
            "height": max(1, int(self.winfo_height())),
        }

    def _set_status(self, text: str, color: str) -> None:
        self.dot_status.configure(text_color=color)
        if self._locked:
            self.mode_label.configure(text=f"锁定穿透 · {text}", text_color=color)
        else:
            self.mode_label.configure(text=f"编辑模式 · {text}", text_color=color)

    def _append_message(self, text: str, color: str = COLOR_PAPER) -> None:
        safe = html.unescape(text)
        self._insert_colored_text(safe, color=color)

    def _update_region_label(self) -> None:
        if self._visual_state != "setup":
            return
        region = self._current_capture_region()
        lock_text = "锁定穿透" if self._locked else "可拖拽/可缩放"
        self.region_label.configure(
            text=(
                f"区域: x={region['left']} y={region['top']} "
                f"w={region['width']} h={region['height']} | {lock_text}"
            )
        )

    def _on_close(self) -> None:
        self._closing = True
        self._capture_pending = False
        self._cancel_prefetch()
        self._cancel_glass_hide()
        self._clear_inplace_labels()
        try:
            if keyboard is not None:
                keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            future = self._runtime.submit(self._api_client.aclose())
            future.result(timeout=1.0)
        except Exception:
            pass
        self._runtime.stop()
        self.destroy()
