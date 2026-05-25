"""OW-Light-Translator 配置模块：DTO 定义与环境变量加载。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API 端点与模型
# ---------------------------------------------------------------------------
GLM_OCR_URL: str = os.getenv(
    "GLM_OCR_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"
)
GLM_OCR_MODEL: str = os.getenv("GLM_OCR_MODEL", "glm-ocr")

DEEPSEEK_URL: str = os.getenv(
    "DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"
)
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

# ---------------------------------------------------------------------------
# 热键与 UI
# ---------------------------------------------------------------------------
HOTKEY_CAPTURE: str = os.getenv("HOTKEY_CAPTURE", "f8")
HOTKEY_TOGGLE_LOCK: str = os.getenv("HOTKEY_TOGGLE_LOCK", "f9")

OVERLAY_OPACITY: float = float(os.getenv("OVERLAY_OPACITY", "0.92"))
FONT_FAMILY: str = os.getenv("FONT_FAMILY", "Microsoft YaHei UI")
FONT_SIZE: int = int(os.getenv("FONT_SIZE", "14"))

# ---------------------------------------------------------------------------
# 本地英文过滤（纯 ASCII 字母/数字/标点则跳过翻译）
# ---------------------------------------------------------------------------
ENGLISH_ONLY_PATTERN: re.Pattern[str] = re.compile(
    r"^[\x00-\x7F\s]*$"  # 仅 ASCII 可打印字符与空白
)

HTTP_TIMEOUT_SEC: float = float(os.getenv("HTTP_TIMEOUT_SEC", "30.0"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))


@dataclass(frozen=True, slots=True)
class CaptureData:
    """屏幕截图内存数据（Base64，零磁盘 I/O）。"""

    base64_png: str
    width: int
    height: int
    region: tuple[int, int, int, int]  # left, top, width, height
    captured_at: float  # time.monotonic() 时间戳


@dataclass(frozen=True, slots=True)
class OCRResult:
    """GLM-OCR 识别结果。"""

    raw_text: str
    skipped: bool = False  # True 表示本地过滤后未调用翻译
    skip_reason: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None and bool(self.raw_text.strip())

    def should_translate(self) -> bool:
        """纯英文/数字/标点则无需翻译。"""
        text = self.raw_text.strip()
        if not text:
            return False
        return not ENGLISH_ONLY_PATTERN.fullmatch(text)


@dataclass(frozen=True, slots=True)
class TransResult:
    """DeepSeek 翻译结果。"""

    source_text: str
    translated_text: str
    latency_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None and bool(self.translated_text.strip())


@dataclass
class AppConfig:
    """运行时配置聚合（便于依赖注入与测试）。"""

    glm_api_key: str = field(default_factory=lambda: GLM_API_KEY)
    deepseek_api_key: str = field(default_factory=lambda: DEEPSEEK_API_KEY)
    glm_ocr_url: str = field(default_factory=lambda: GLM_OCR_URL)
    glm_ocr_model: str = field(default_factory=lambda: GLM_OCR_MODEL)
    deepseek_url: str = field(default_factory=lambda: DEEPSEEK_URL)
    deepseek_model: str = field(default_factory=lambda: DEEPSEEK_MODEL)
    hotkey_capture: str = field(default_factory=lambda: HOTKEY_CAPTURE)
    hotkey_toggle_lock: str = field(default_factory=lambda: HOTKEY_TOGGLE_LOCK)
    http_timeout_sec: float = field(default_factory=lambda: HTTP_TIMEOUT_SEC)
    max_retries: int = field(default_factory=lambda: MAX_RETRIES)

    def validate(self) -> list[str]:
        """返回缺失配置的警告列表。"""
        warnings: list[str] = []
        if not self.glm_api_key:
            warnings.append("GLM_API_KEY 未设置，OCR 将不可用。")
        if not self.deepseek_api_key:
            warnings.append("DEEPSEEK_API_KEY 未设置，翻译将不可用。")
        return warnings


def get_app_config() -> AppConfig:
    return AppConfig()
