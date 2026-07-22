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
    "GLM_OCR_URL", "https://open.bigmodel.cn/api/paas/v4/layout_parsing"
)
GLM_OCR_MODEL: str = os.getenv("GLM_OCR_MODEL", "glm-ocr")
GLM_API_KEY: str = (FILE_GLM_API_KEY or os.getenv("GLM_API_KEY", "")).strip()

DEEPSEEK_URL: str = os.getenv(
    "DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"
)
# deepseek-v4-flash + thinking=disabled ≈ 原 deepseek-chat（非思考）快路径
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_API_KEY: str = (FILE_DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")).strip()
# 关闭 thinking，否则 v4-flash 默认开启 CoT，无法压到 1s 内
DEEPSEEK_THINKING_DISABLED: bool = os.getenv(
    "DEEPSEEK_THINKING_DISABLED", "1"
).strip().lower() not in {"0", "false", "no", "off"}
DEEPSEEK_MAX_TOKENS: int = max(64, int(os.getenv("DEEPSEEK_MAX_TOKENS", "256")))

HTTP_TIMEOUT_SEC: float = float(os.getenv("HTTP_TIMEOUT_SEC", "18"))
OCR_MAX_CONCURRENT: int = max(1, int(os.getenv("OCR_MAX_CONCURRENT", "3")))
OCR_CHANNELS: tuple[str, ...] = tuple(
    label.strip()
    for label in os.getenv("OCR_CHANNELS", "Friendly,Group,Alert").split(",")
    if label.strip()
)
# hybrid=词典/行缓存优先 + OCR + 仅对未命中行调 LLM
# oneshot=单次视觉模型（实验，需 PIPELINE_VISION_URL）
PIPELINE_MODE: str = os.getenv("PIPELINE_MODE", "hybrid").strip().lower()
# 锁定态后台预取 OCR，F8 只补翻译缺口
PREFETCH_ENABLED: bool = os.getenv("PREFETCH_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
PREFETCH_INTERVAL_MS: int = max(200, int(os.getenv("PREFETCH_INTERVAL_MS", "800")))
# 译文原位覆盖：用 OCR bbox 画在毛玻璃上盖住原文
INPLACE_OVERLAY: bool = os.getenv("INPLACE_OVERLAY", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


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
class OCRLine:
    """单行 OCR：文本 + 相对截图区域的归一化 bbox (x0,y0,x1,y1) ∈ [0,1]。"""

    text: str
    bbox: Optional[tuple[float, float, float, float]] = None


@dataclass(frozen=True, slots=True)
class OCRResult:
    """OCR 文本块与其原始语义颜色。"""

    raw_text: str
    is_valid: bool
    color_tag: Optional[ColorTag] = None
    error_msg: Optional[str] = None
    lines: tuple[OCRLine, ...] = ()


@dataclass(frozen=True, slots=True)
class TransResult:
    """翻译结果：保留来源文本和颜色语义。"""

    source_text: str
    translated: str
    color_tag: Optional[ColorTag] = None
    status_code: int = 200  # 200: 成功
    # 相对 Overlay 选区的归一化 bbox；用于原位覆盖原文
    bbox: Optional[tuple[float, float, float, float]] = None
    # dict=俚语词典 | memory=行缓存 | llm=模型 | passthrough=原文兜底
    source: str = "llm"


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

# TODO(#3): 支持玩家自定义聊天颜色主题（非默认颜色）。
# TODO(#4): 建议新增 color_palette.json 或环境变量覆盖，并在配置非法时回退默认值。
# 便于按 label O(1) 查找颜色标签
COLOR_TAG_MAP: Dict[str, ColorTag] = {tag.label: tag for tag in COLOR_PALETTE}
