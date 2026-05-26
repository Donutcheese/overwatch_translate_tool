"""Overlay window implementation."""

from __future__ import annotations

import asyncio
import ctypes
import html
import os
import sys
from concurrent.futures import Future
from typing import Any

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.config import TransResult
from ..runtime.async_runtime import AsyncRuntime
from ..services.api_client import OWColorFluentApiClient, capture_region_to_base64

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - 在不支持平台上兜底
    keyboard = None


HOTKEY_CAPTURE: str = os.getenv("HOTKEY_CAPTURE", "f8")
HOTKEY_TOGGLE_LOCK: str = os.getenv("HOTKEY_TOGGLE_LOCK", "f9")


class OverlayWindow(QMainWindow):
    """主悬浮窗：可拖拽/缩放，支持锁定穿透与热键触发识别。"""

    pipeline_done = pyqtSignal(object, str)  # data, error
    capture_hotkey_fired = pyqtSignal()
    lock_hotkey_fired = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._runtime = AsyncRuntime()

        self._locked = False
        self._busy = False
        self._dragging = False
        self._resizing = False
        self._drag_offset = QPoint()
        self._resize_start_global = QPoint()
        self._resize_start_rect = QRect()
        self._header_height = 42
        self._resize_handle_size = 16

        # TODO(#1): 校准 Overlay 默认尺寸与最小尺寸，使其更贴合 OW 聊天框比例。
        # TODO(#2): 增加分辨率预设（16:9 / 21:9 / 16:10）并在运行时快速切换。
        self.setWindowTitle("OW-Color-Fluent-Translator")
        self.setMinimumSize(360, 220)
        self.resize(540, 340)
        self.move(220, 180)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._build_ui()
        self._connect_signals()
        self._register_hotkeys()
        self._apply_lock_mode(False)
        self._update_region_label()
        self._set_status("待命", "#6EE7B7")

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("card")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)
        outer.addWidget(self.card)

        header = QHBoxLayout()
        header.setSpacing(8)
        card_layout.addLayout(header)

        self.dot_status = QLabel("●")
        self.dot_status.setFixedWidth(14)
        self.dot_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.dot_status)

        self.title_label = QLabel("OW Color Fluent Translator")
        self.title_label.setObjectName("title")
        header.addWidget(self.title_label, 1)

        self.mode_label = QLabel("编辑模式")
        self.mode_label.setObjectName("mode")
        header.addWidget(self.mode_label)

        self.capture_btn = QPushButton(f"识别({HOTKEY_CAPTURE.upper()})")
        self.capture_btn.setObjectName("btnPrimary")
        header.addWidget(self.capture_btn)

        self.lock_btn = QPushButton(f"锁定({HOTKEY_TOGGLE_LOCK.upper()})")
        self.lock_btn.setObjectName("btn")
        header.addWidget(self.lock_btn)

        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("btnClose")
        self.close_btn.setFixedWidth(28)
        header.addWidget(self.close_btn)

        self.region_label = QLabel()
        self.region_label.setObjectName("hint")
        card_layout.addWidget(self.region_label)

        self.result_view = QTextBrowser()
        self.result_view.setObjectName("result")
        self.result_view.setOpenExternalLinks(False)
        self.result_view.setReadOnly(True)
        self.result_view.setText("等待识别...\n使用热键触发识别。")
        card_layout.addWidget(self.result_view, 1)

        self.resize_tip = QLabel("◢")
        self.resize_tip.setObjectName("hint")
        self.resize_tip.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        )
        card_layout.addWidget(self.resize_tip, 0, Qt.AlignmentFlag.AlignRight)

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#card {
                background: rgba(15, 23, 42, 220);
                border: 1px solid rgba(148, 163, 184, 120);
                border-radius: 12px;
            }
            QLabel#title {
                color: #E2E8F0;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#mode {
                color: #93C5FD;
                font-size: 12px;
            }
            QLabel#hint {
                color: #94A3B8;
                font-size: 12px;
            }
            QPushButton#btnPrimary {
                background: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton#btnPrimary:hover { background: #1D4ED8; }
            QPushButton#btn {
                background: #334155;
                color: #E2E8F0;
                border: none;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton#btn:hover { background: #475569; }
            QPushButton#btnClose {
                background: #7F1D1D;
                color: #FEE2E2;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#btnClose:hover { background: #991B1B; }
            QTextBrowser#result {
                background: rgba(2, 6, 23, 190);
                border: 1px solid rgba(71, 85, 105, 120);
                border-radius: 10px;
                color: #E2E8F0;
                font-size: 13px;
                padding: 8px;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.capture_btn.clicked.connect(self.trigger_capture)
        self.lock_btn.clicked.connect(self.toggle_lock_mode)
        self.close_btn.clicked.connect(self.close)
        self.pipeline_done.connect(self._handle_pipeline_done)
        self.capture_hotkey_fired.connect(self.trigger_capture)
        self.lock_hotkey_fired.connect(self.toggle_lock_mode)

    def _register_hotkeys(self) -> None:
        if keyboard is None:
            self._append_message("热键库不可用：将仅支持按钮触发。", "#F59E0B")
            return
        try:
            keyboard.add_hotkey(
                HOTKEY_CAPTURE, lambda: self.capture_hotkey_fired.emit(), suppress=False
            )
            keyboard.add_hotkey(
                HOTKEY_TOGGLE_LOCK,
                lambda: self.lock_hotkey_fired.emit(),
                suppress=False,
            )
        except Exception as exc:
            self._append_message(f"热键注册失败：{exc}", "#F59E0B")

    def trigger_capture(self) -> None:
        if self._busy:
            return
        region = self._current_capture_region()
        if region["width"] < 80 or region["height"] < 60:
            self._append_message("截图区域过小，请扩大窗口。", "#F59E0B")
            return

        self._busy = True
        self._set_status("识别中", "#60A5FA")

        self.hide()
        QTimer.singleShot(90, lambda: self._launch_pipeline(region))
        QTimer.singleShot(180, self.show)

    def _launch_pipeline(self, region: dict[str, int]) -> None:
        future = self._runtime.submit(self._pipeline(region))
        future.add_done_callback(self._on_pipeline_future_done)

    def _on_pipeline_future_done(self, future: Future) -> None:
        try:
            payload = future.result()
            self.pipeline_done.emit(payload, "")
        except Exception as exc:
            self.pipeline_done.emit(None, str(exc))

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

    def update_translation_list(self, results: list[TransResult]) -> None:
        lines: list[str] = []
        for item in results:
            color = "#E2E8F0"
            label = "Unknown"
            if item.color_tag is not None:
                color = item.color_tag.hex_color
                label = item.color_tag.label
            text = html.escape(item.translated.strip() or "(空)")
            lines.append(
                f'<div style="margin-bottom:6px;">'
                f'<span style="color:{color};font-weight:700;">[{label}]</span> '
                f'<span style="color:{color};">{text}</span></div>'
            )
        self.result_view.setHtml("".join(lines))

    def _render_ocr_fallback(self, ocr_results: list[Any]) -> None:
        if not ocr_results:
            self.result_view.setText("无可用 OCR 结果。")
            return
        lines: list[str] = []
        for item in ocr_results:
            label = getattr(getattr(item, "color_tag", None), "label", "Unknown")
            msg = getattr(item, "error_msg", None) or "无文本输出"
            lines.append(f"[{label}] {msg}")
        self.result_view.setText("\n".join(lines))

    def toggle_lock_mode(self) -> None:
        self._apply_lock_mode(not self._locked)

    def _apply_lock_mode(self, locked: bool) -> None:
        self._locked = locked
        if locked:
            self.mode_label.setText("锁定穿透")
            self.lock_btn.setText(f"解锁({HOTKEY_TOGGLE_LOCK.upper()})")
            self.resize_tip.hide()
            self._set_click_through(True)
        else:
            self.mode_label.setText("编辑模式")
            self.lock_btn.setText(f"锁定({HOTKEY_TOGGLE_LOCK.upper()})")
            self.resize_tip.show()
            self._set_click_through(False)
        self._update_region_label()

    def _set_click_through(self, enabled: bool) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if sys.platform.startswith("win"):
            try:
                hwnd = int(self.winId())
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x00080000
                WS_EX_TRANSPARENT = 0x00000020
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style |= WS_EX_LAYERED
                if enabled:
                    style |= WS_EX_TRANSPARENT
                else:
                    style &= ~WS_EX_TRANSPARENT
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            except Exception:
                pass

    def mousePressEvent(self, event: Any) -> None:
        if self._locked or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        pos = event.position().toPoint()
        if self._is_on_resize_handle(pos):
            self._resizing = True
            self._resize_start_global = event.globalPosition().toPoint()
            self._resize_start_rect = self.geometry()
            return

        child = self.childAt(pos)
        if isinstance(child, (QPushButton, QTextBrowser)):
            super().mousePressEvent(event)
            return

        if pos.y() <= self._header_height:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._locked:
            super().mouseMoveEvent(event)
            return
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._update_region_label()
        elif self._resizing:
            delta = event.globalPosition().toPoint() - self._resize_start_global
            new_w = max(self.minimumWidth(), self._resize_start_rect.width() + delta.x())
            new_h = max(self.minimumHeight(), self._resize_start_rect.height() + delta.y())
            self.resize(new_w, new_h)
            self._update_region_label()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._dragging = False
        self._resizing = False
        super().mouseReleaseEvent(event)

    def moveEvent(self, event: Any) -> None:
        self._update_region_label()
        super().moveEvent(event)

    def resizeEvent(self, event: Any) -> None:
        self._update_region_label()
        super().resizeEvent(event)

    def _is_on_resize_handle(self, pos: QPoint) -> bool:
        rect = self.rect()
        return (
            rect.width() - self._resize_handle_size <= pos.x() <= rect.width()
            and rect.height() - self._resize_handle_size <= pos.y() <= rect.height()
        )

    def _current_capture_region(self) -> dict[str, int]:
        geo = self.frameGeometry()
        return {
            "left": max(0, geo.x()),
            "top": max(0, geo.y()),
            "width": max(1, geo.width()),
            "height": max(1, geo.height()),
        }

    def _set_status(self, text: str, color: str) -> None:
        self.dot_status.setStyleSheet(f"color:{color}; font-size: 14px;")
        self.mode_label.setStyleSheet(f"color:{color}; font-size: 12px;")
        if self._locked:
            self.mode_label.setText(f"锁定穿透 · {text}")
        else:
            self.mode_label.setText(f"编辑模式 · {text}")

    def _append_message(self, text: str, color: str = "#E2E8F0") -> None:
        safe = html.escape(text)
        self.result_view.append(f'<span style="color:{QColor(color).name()};">{safe}</span>')

    def _update_region_label(self) -> None:
        region = self._current_capture_region()
        lock_text = "锁定穿透" if self._locked else "可拖拽/可缩放"
        self.region_label.setText(
            f"区域: x={region['left']} y={region['top']} "
            f"w={region['width']} h={region['height']} | {lock_text}"
        )

    def closeEvent(self, event: Any) -> None:
        try:
            if keyboard is not None:
                keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._runtime.stop()
        super().closeEvent(event)

