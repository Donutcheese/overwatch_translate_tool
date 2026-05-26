"""项目全局配置与基础 DTO 定义。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv

try:
    from local_api_keys import DEEPSEEK_API_KEY as FILE_DEEPSEEK_API_KEY
    from local_api_keys import GLM_API_KEY as FILE_GLM_API_KEY
except ImportError:
    FILE_DEEPSEEK_API_KEY = ""
    FILE_GLM_API_KEY = ""

load_dotenv()

# API 与模型配置（后续 `api_client.py` 直接复用）
GLM_OCR_URL: str = os.getenv(
    "GLM_OCR_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"
)
GLM_OCR_MODEL: str = os.getenv("GLM_OCR_MODEL", "glm-ocr")
GLM_API_KEY: str = (FILE_GLM_API_KEY or os.getenv("GLM_API_KEY", "")).strip()

DEEPSEEK_URL: str = os.getenv(
    "DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"
)
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY: str = (FILE_DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")).strip()

HTTP_TIMEOUT_SEC: float = float(os.getenv("HTTP_TIMEOUT_SEC", "30"))


@dataclass(frozen=True, slots=True)
class CaptureData:
    """捕获截图及元数据。"""

    image_base64: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ColorTag:
    """语义颜色标签与对应 RGB 掩码范围。"""

    label: str  # 'Enemy', 'Friendly', 'Group', 'Alert'
    hex_color: str  # 用于 UI 渲染，例如 '#FF0000'
    rgb_min: tuple[int, int, int]  # 例如 (100, 0, 0)
    rgb_max: tuple[int, int, int]  # 例如 (255, 100, 100)


@dataclass(frozen=True, slots=True)
class OCRResult:
    """OCR 文本块与其原始语义颜色。"""

    raw_text: str
    is_valid: bool
    color_tag: Optional[ColorTag] = None
    error_msg: Optional[str] = None


@dataclass(frozen=True, slots=True)
class TransResult:
    """翻译结果：保留来源文本和颜色语义。"""

    source_text: str
    translated: str
    color_tag: Optional[ColorTag] = None
    status_code: int = 200  # 200: 成功


COLOR_PALETTE: List[ColorTag] = [
    ColorTag(
        label="Enemy",
        hex_color="#FF4C4C",
        rgb_min=(150, 0, 0),
        rgb_max=(255, 100, 100),
    ),
    ColorTag(
        label="Friendly",
        hex_color="#4CBFFF",
        rgb_min=(0, 100, 150),
        rgb_max=(100, 200, 255),
    ),
    ColorTag(
        label="Group",
        hex_color="#4CFF4C",
        rgb_min=(0, 150, 0),
        rgb_max=(100, 255, 100),
    ),
    ColorTag(
        label="Alert",
        hex_color="#FF8000",
        rgb_min=(150, 100, 0),
        rgb_max=(255, 200, 100),
    ),
]

# 便于按 label O(1) 查找颜色标签
COLOR_TAG_MAP: Dict[str, ColorTag] = {tag.label: tag for tag in COLOR_PALETTE}
