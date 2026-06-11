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

from ..core.config import TransResult
from ..runtime.async_runtime import AsyncRuntime
from ..services.api_client import OWColorFluentApiClient, capture_region_to_base64

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
# 1080p 下悬浮窗高度为 MIN_HEIGHT，以此为字体与控件缩放基准
BASE_REFERENCE_HEIGHT = MIN_HEIGHT


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
        self._last_scaled_h = 0

        self.title("OW-Color-Fluent-Translator")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=TRANSPARENT_COLOR)
        self.attributes("-transparentcolor", TRANSPARENT_COLOR)

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

        self._insert_colored_text("等待识别...", newline=True)
        self._insert_colored_text("使用热键触发识别。", color="#94A3B8")

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
        self.update_idletasks()

    def _init_font_scale_from_screen(self) -> None:
        _, screen_h = self._get_screen_size()
        height = max(MIN_HEIGHT, int(screen_h / 6))
        self._set_font_scale_from_height(height)

    def _set_font_scale_from_height(self, height: int) -> None:
        self._font_scale = max(1.0, height / BASE_REFERENCE_HEIGHT)
        self._resize_handle_size = max(16, int(height * 0.09))
        self._last_scaled_h = height

    def _font_size(self, base: int) -> int:
        return max(9, int(round(base * self._font_scale)))

    def _scaled_px(self, base: int) -> int:
        return max(1, int(round(base * self._font_scale)))

    def _scaled_font(self, base_size: int, weight: str = "normal") -> tkfont.Font:
        return tkfont.Font(
            family="Segoe UI",
            size=self._font_size(base_size),
            weight=weight,
        )

    def _apply_ui_scale(self) -> None:
        dot_w = self._scaled_px(14)
        btn_w = self._scaled_px(90)
        btn_h = self._scaled_px(28)
        close_sz = self._scaled_px(28)

        self.dot_status.configure(width=dot_w, font=self._scaled_font(14))
        self.title_label.configure(font=self._scaled_font(14, "bold"))
        self.mode_label.configure(font=self._scaled_font(12))
        self.capture_btn.configure(
            width=btn_w,
            height=btn_h,
            font=self._scaled_font(12),
        )
        self.lock_btn.configure(
            width=btn_w,
            height=btn_h,
            font=self._scaled_font(12),
        )
        self.close_btn.configure(
            width=close_sz,
            height=close_sz,
            font=self._scaled_font(14, "bold"),
        )
        self.region_label.configure(font=self._scaled_font(12))
        self.result_view.configure(font=self._scaled_font(13))
        self.resize_tip.configure(
            width=self._resize_handle_size,
            height=self._resize_handle_size,
            font=self._scaled_font(12),
        )

    def _maybe_apply_ui_scale(self) -> None:
        height = int(self.winfo_height())
        if height < MIN_HEIGHT:
            return
        if abs(height - self._last_scaled_h) < 2:
            return
        self._last_scaled_h = height
        self._set_font_scale_from_height(height)
        self._apply_ui_scale()

    def _build_ui(self) -> None:
        self.card = ctk.CTkFrame(
            self,
            fg_color="#0F172A",
            corner_radius=12,
            border_width=1,
            border_color="#94A3B8",
        )
        self.card.pack(fill="both", expand=True, padx=10, pady=10)

        self.header = ctk.CTkFrame(self.card, fg_color="transparent")
        self.header.pack(fill="x", padx=4, pady=(4, 0))

        self.dot_status = ctk.CTkLabel(
            self.header,
            text="●",
            width=self._scaled_px(14),
            font=self._scaled_font(14),
            text_color="#6EE7B7",
        )
        self.dot_status.pack(side="left", padx=(0, 4))

        self.title_label = ctk.CTkLabel(
            self.header,
            text="OW Color Fluent Translator",
            font=self._scaled_font(14, "bold"),
            text_color="#E2E8F0",
            anchor="w",
        )
        self.title_label.pack(side="left", fill="x", expand=True)

        self.mode_label = ctk.CTkLabel(
            self.header,
            text="编辑模式",
            font=self._scaled_font(12),
            text_color="#93C5FD",
        )
        self.mode_label.pack(side="left", padx=(8, 8))

        self.capture_btn = ctk.CTkButton(
            self.header,
            text=f"识别({HOTKEY_CAPTURE.upper()})",
            width=self._scaled_px(90),
            height=self._scaled_px(28),
            font=self._scaled_font(12),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.trigger_capture,
        )
        self.capture_btn.pack(side="left", padx=(0, 4))

        self.lock_btn = ctk.CTkButton(
            self.header,
            text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})",
            width=self._scaled_px(90),
            height=self._scaled_px(28),
            font=self._scaled_font(12),
            fg_color="#334155",
            hover_color="#475569",
            command=self.toggle_lock_mode,
        )
        self.lock_btn.pack(side="left", padx=(0, 4))

        self.close_btn = ctk.CTkButton(
            self.header,
            text="×",
            width=self._scaled_px(28),
            height=self._scaled_px(28),
            font=self._scaled_font(14, "bold"),
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self._on_close,
        )
        self.close_btn.pack(side="left")

        self.region_label = ctk.CTkLabel(
            self.card,
            text="",
            font=self._scaled_font(12),
            text_color="#94A3B8",
            anchor="w",
        )
        self.region_label.pack(fill="x", padx=8, pady=(6, 4))

        self.result_view = ctk.CTkTextbox(
            self.card,
            font=self._scaled_font(13),
            fg_color="#020617",
            border_color="#475569",
            border_width=1,
            text_color="#E2E8F0",
            wrap="word",
            activate_scrollbars=True,
        )
        self.result_view.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.resize_tip = ctk.CTkLabel(
            self.card,
            text="◢",
            font=self._scaled_font(12),
            text_color="#94A3B8",
            width=self._resize_handle_size,
            height=self._resize_handle_size,
        )
        self.resize_tip.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)

        drag_widgets = (
            self.header,
            self.dot_status,
            self.title_label,
            self.mode_label,
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

    def trigger_capture(self) -> None:
        if self._busy:
            return
        region = self._current_capture_region()
        if region["width"] < 80 or region["height"] < 60:
            self._append_message("截图区域过小，请扩大窗口。", "#F59E0B")
            return

        self._busy = True
        self._set_status("识别中", "#60A5FA")

        self.withdraw()
        self.after(90, lambda: self._launch_pipeline(region))
        self.after(180, self._restore_after_capture)

    def _restore_after_capture(self) -> None:
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()

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
        font = self._scaled_font(13, weight)
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
            self.resize_tip.place_forget()
            self._set_click_through(True)
        else:
            self.mode_label.configure(text="编辑模式")
            self.lock_btn.configure(text=f"锁定({HOTKEY_TOGGLE_LOCK.upper()})")
            self.resize_tip.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
            self._set_click_through(False)
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
