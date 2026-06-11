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

from ..core.config import GLM_API_KEY, TransResult
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

# 毛玻璃面板自动隐藏（毫秒，锁定模式下）
GLASS_AUTO_HIDE_MS = int(os.getenv("GLASS_AUTO_HIDE_MS", "12000"))

# 视觉样式（glass 模式用 transparent 让 DWM 模糊透出）
COLOR_CARD_SETUP = "#1E293B"
COLOR_CARD_BORDER = "#64748B"
COLOR_TEXTBOX_SETUP = "#0F172A"
# 毛玻璃模式下根窗口底色（非 colorkey，供 DWM 合成）
GLASS_ROOT_BG = "#0A0E17"


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
        ctk.set_default_color_theme("blue")

        super().__init__()

        self._runtime = AsyncRuntime()
        self._locked = False
        self._busy = False
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
        self._set_status("待命", "#6EE7B7")
        self.result_view.delete("1.0", "end")
        if not GLM_API_KEY.strip():
            self._insert_colored_text(
                "GLM_API_KEY 未配置：请在项目根目录创建 local_api_keys.py",
                color="#F59E0B",
            )
            self._insert_colored_text("示例：GLM_API_KEY = \"你的智谱Key\"", color="#94A3B8")
        else:
            self._insert_colored_text("F8 识别 · F9 锁定后游戏中透明", color="#94A3B8")

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
            text_color="#6EE7B7",
        )
        self.dot_status.grid(row=0, column=0, padx=(0, 4))

        self.title_label = ctk.CTkLabel(
            self.header,
            text="OW Translator",
            font=self._scaled_font(FONT_BASE_TITLE, "bold"),
            text_color="#E2E8F0",
            anchor="w",
        )
        self.title_label.grid(row=0, column=1, sticky="ew")

        self.header_actions = ctk.CTkFrame(self.header, fg_color="transparent")
        self.header_actions.grid(row=0, column=2, sticky="e")

        self.mode_label = ctk.CTkLabel(
            self.header_actions,
            text="编辑模式",
            font=self._scaled_font(FONT_BASE_MODE),
            text_color="#93C5FD",
        )
        self.mode_label.pack(side="left", padx=(0, 6))

        self.capture_btn = ctk.CTkButton(
            self.header_actions,
            text=f"识别({HOTKEY_CAPTURE.upper()})",
            width=self._scaled_px(72),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_BTN),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.trigger_capture,
        )
        self.capture_btn.pack(side="left", padx=(0, 4))

        self.lock_btn = ctk.CTkButton(
            self.header_actions,
            text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})",
            width=self._scaled_px(72),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_BTN),
            fg_color="#334155",
            hover_color="#475569",
            command=self.toggle_lock_mode,
        )
        self.lock_btn.pack(side="left", padx=(0, 4))

        self.close_btn = ctk.CTkButton(
            self.header_actions,
            text="×",
            width=self._scaled_px(24),
            height=self._scaled_px(24),
            font=self._scaled_font(FONT_BASE_TITLE, "bold"),
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self._on_close,
        )
        self.close_btn.pack(side="left")

        self.region_label = ctk.CTkLabel(
            self.card,
            text="",
            font=self._scaled_font(FONT_BASE_REGION),
            text_color="#94A3B8",
            anchor="w",
        )
        self.region_label.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))

        self.result_view = ctk.CTkTextbox(
            self.card,
            font=self._scaled_font(FONT_BASE_BODY),
            fg_color=COLOR_TEXTBOX_SETUP,
            border_color="#475569",
            border_width=1,
            text_color="#E2E8F0",
            wrap="word",
            activate_scrollbars=True,
        )
        self.result_view.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))

        self.footer = ctk.CTkFrame(self.card, fg_color="transparent", height=self._scaled_px(18))
        self.footer.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 2))
        self.footer.grid_columnconfigure(0, weight=1)

        self.resize_tip = ctk.CTkLabel(
            self.footer,
            text="◢",
            font=self._scaled_font(FONT_BASE_REGION),
            text_color="#64748B",
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
            self._append_message("热键库不可用：将仅支持按钮触发。", "#F59E0B")
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
            self._append_message(f"热键注册失败：{exc}", "#F59E0B")

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
        if self._visual_state == "glass":
            enabled = False
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
            self._set_visual_state("hidden")

    def _set_root_colorkey(self, enabled: bool) -> None:
        """colorkey 透明与 DWM 毛玻璃互斥；glass 模式必须关闭 colorkey。"""
        if enabled:
            self.configure(fg_color=TRANSPARENT_COLOR)
            self.attributes("-transparentcolor", TRANSPARENT_COLOR)
        else:
            try:
                self.attributes("-transparentcolor", "")
            except Exception:
                pass
            self.configure(fg_color=GLASS_ROOT_BG)

    def _apply_acrylic(self, enabled: bool) -> None:
        if not sys.platform.startswith("win"):
            return

        def _run() -> None:
            self.update_idletasks()
            set_acrylic_blur(self._get_hwnd(), enabled)

        self.after(50, _run)

    def _show_setup_widgets(self) -> None:
        self.card.grid_rowconfigure(0, weight=0)
        self.card.grid_rowconfigure(2, weight=1)
        self.header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        self.region_label.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 2))
        self.result_view.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 2))
        if not self._locked:
            self.footer.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 2))

    def _hide_setup_widgets(self) -> None:
        self.header.grid_remove()
        self.region_label.grid_remove()
        self.footer.grid_remove()

    def _set_visual_state(self, state: str) -> None:
        """setup=编辑对齐 | hidden=游戏中全透明 | glass=F8 后毛玻璃译文。"""
        self._visual_state = state
        self._cancel_glass_hide()

        if state == "hidden":
            self._set_root_colorkey(True)
            self.card.configure(fg_color=TRANSPARENT_COLOR, border_width=0)
            self.result_view.configure(fg_color=TRANSPARENT_COLOR, border_width=0)
            self._hide_setup_widgets()
            self.result_view.grid_remove()
            self._apply_acrylic(False)
            if self._locked:
                self._set_click_through(True)
            return

        if state == "setup":
            self._set_root_colorkey(True)
            self.card.configure(
                fg_color=COLOR_CARD_SETUP,
                border_width=1,
                border_color=COLOR_CARD_BORDER,
            )
            self.result_view.configure(
                fg_color=COLOR_TEXTBOX_SETUP,
                border_width=1,
                border_color="#475569",
            )
            self._show_setup_widgets()
            self._apply_acrylic(False)
            self._set_click_through(False)
            self._refresh_font_scale_from_window()
            return

        if state == "glass":
            self._set_root_colorkey(False)
            self.card.configure(fg_color="transparent", border_width=1, border_color="#94A3B8")
            self.result_view.configure(fg_color="transparent", border_width=0)
            self._hide_setup_widgets()
            self.result_view.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            self.card.grid_rowconfigure(0, weight=1)
            self._apply_acrylic(True)
            self._set_click_through(False)
            self._refresh_font_scale_from_window()
            self._schedule_glass_hide()

    def trigger_capture(self) -> None:
        if self._busy:
            return
        region = self._current_capture_region()
        if region["width"] < 80 or region["height"] < 60:
            if self._locked:
                self._set_visual_state("glass")
            self._append_message("截图区域过小，请扩大窗口。", "#F59E0B")
            return

        self._busy = True
        self._set_status("识别中", "#60A5FA")

        if self._locked:
            self._set_visual_state("glass")
            self.result_view.delete("1.0", "end")
            self._insert_colored_text("识别中...", color="#60A5FA", newline=False)
        else:
            self._set_visual_state("setup")

        self.withdraw()
        self.after(90, lambda: self._launch_pipeline(region))
        self.after(180, self._restore_after_capture)

    def _restore_after_capture(self) -> None:
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        if self._locked:
            self._set_visual_state("glass")
        else:
            self._set_visual_state("setup")

    def _launch_pipeline(self, region: dict[str, int]) -> None:
        future = self._runtime.submit(self._pipeline(region))
        future.add_done_callback(self._on_pipeline_future_done)

    def _on_pipeline_future_done(self, future: Future) -> None:
        try:
            payload = future.result()
            self.after(0, self._handle_pipeline_done, payload, "")
        except Exception as exc:
            self.after(0, self._handle_pipeline_done, None, str(exc))

    async def _pipeline(self, region: dict[str, int]) -> dict[str, Any]:
        capture_data = await asyncio.to_thread(capture_region_to_base64, region)
        async with OWColorFluentApiClient() as client:
            ocr_results = await client.process_multi_channel_ocr(capture_data)
            trans_results = await client.translate_ocr_results(ocr_results)
        return {"ocr": ocr_results, "trans": trans_results}

    def _handle_pipeline_done(self, payload: object, error: str) -> None:
        self._busy = False
        if self._locked:
            self._set_visual_state("glass")
        elif error or not isinstance(payload, dict):
            self._set_visual_state("setup")

        if error:
            self._set_status("失败", "#F87171")
            self._append_message(f"识别失败：{error}", "#F87171")
            return
        if not isinstance(payload, dict):
            self._set_status("失败", "#F87171")
            self._append_message("识别失败：返回结果异常。", "#F87171")
            return

        trans_results = payload.get("trans", [])
        ocr_results = payload.get("ocr", [])

        if trans_results:
            self.update_translation_list(trans_results)
            self._set_status("完成", "#34D399")
        else:
            self._set_status("无结果", "#F59E0B")
            self._render_ocr_fallback(ocr_results)

        if self._locked:
            self._schedule_glass_hide()
        else:
            self._set_visual_state("setup")

    def _insert_colored_text(
        self,
        text: str,
        color: str = "#E2E8F0",
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
        self.result_view.delete("1.0", "end")
        for item in results:
            color = "#E2E8F0"
            label = "Unknown"
            if item.color_tag is not None:
                color = item.color_tag.hex_color
                label = item.color_tag.label
            text = html.unescape(item.translated.strip() or "(空)")
            self._insert_colored_text(f"[{label}] ", color=color, bold=True, newline=False)
            self._insert_colored_text(text, color=color, bold=False, newline=True)

    def _render_ocr_fallback(self, ocr_results: list[Any]) -> None:
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
            self._insert_colored_text(unique[0], color="#F59E0B")
            if "GLM_API_KEY" in unique[0]:
                self._insert_colored_text(
                    "编辑 local_api_keys.py 后重启程序。",
                    color="#94A3B8",
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
        else:
            self.mode_label.configure(text="编辑模式")
            self.lock_btn.configure(text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})")
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

    def _append_message(self, text: str, color: str = "#E2E8F0") -> None:
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
        try:
            if keyboard is not None:
                keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._runtime.stop()
        self.destroy()
