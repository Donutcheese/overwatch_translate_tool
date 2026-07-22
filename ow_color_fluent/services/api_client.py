"""异步 API 客户端：内存截图、多通道 OCR、混合快路径翻译。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import asdict
from typing import Any, Iterable, List, Optional, Sequence

import cv2
import httpx
import mss
import numpy as np

from ..core.config import (
    COLOR_PALETTE,
    COLOR_TAG_MAP,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    DEEPSEEK_THINKING_DISABLED,
    DEEPSEEK_URL,
    GLM_API_KEY,
    GLM_OCR_MODEL,
    GLM_OCR_URL,
    HTTP_TIMEOUT_SEC,
    OCR_CHANNELS,
    OCR_MAX_CONCURRENT,
    CaptureData,
    ColorTag,
    OCRLine,
    OCRResult,
    TransResult,
)
from ..core.prompts import build_translation_messages, build_warmup_messages
from .phrase_cache import (
    GLOBAL_TRANSLATION_MEMORY,
    OW_PHRASE_DICT,
    TranslationMemory,
    normalize_chat_text,
)


_TRANSLATION_CACHE_MAX = 256
_translation_cache: dict[tuple[tuple[str, str], ...], list[TransResult]] = {}
logger = logging.getLogger(__name__)


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def capture_region_to_base64(region: dict[str, int]) -> CaptureData:
    """使用 `mss` 捕获指定区域并转为 PNG Base64（纯内存）。"""
    started = time.perf_counter()
    with mss.mss() as sct:
        shot = sct.grab(region)
        bgra_frame = np.array(shot, dtype=np.uint8)

    bgr_frame = cv2.cvtColor(bgra_frame, cv2.COLOR_BGRA2BGR)
    ok, encoded = cv2.imencode(".png", bgr_frame)
    if not ok:
        raise RuntimeError("截图编码失败：无法将内存图像编码为 PNG。")

    image_base64 = base64.b64encode(encoded.tobytes()).decode("utf-8")
    logger.info(
        "capture_region_to_base64: %.1fms region=%sx%s",
        _elapsed_ms(started),
        bgr_frame.shape[1],
        bgr_frame.shape[0],
    )
    return CaptureData(
        image_base64=image_base64,
        width=bgr_frame.shape[1],
        height=bgr_frame.shape[0],
    )


def decode_base64_image_to_bgr(image_base64: str) -> np.ndarray:
    """将 Base64 图像解码为 BGR 格式 `numpy.ndarray`。"""
    raw = base64.b64decode(image_base64.encode("utf-8"))
    array = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Base64 图像解码失败：请检查图片数据格式。")
    return image


def encode_bgr_image_to_base64(image_bgr: np.ndarray) -> str:
    """将 BGR 图像编码为 PNG Base64。"""
    ok, encoded = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("图像编码失败：无法将 BGR 图编码为 PNG。")
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def encode_bgr_image_to_jpeg_data_uri(
    image_bgr: np.ndarray, *, quality: int = 90
) -> str:
    """将 BGR 图像编码为 GLM-OCR 接受的 JPEG Data URI。"""
    ok, encoded = cv2.imencode(
        ".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    if not ok:
        raise RuntimeError("图像编码失败：无法将 BGR 图编码为 JPEG。")
    b64 = base64.b64encode(encoded.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _mask_has_foreground(masked_gray: np.ndarray, *, min_pixels: int = 16) -> bool:
    """掩码图中是否存在足够的前景像素，避免向 OCR 发送空白图。"""
    return int(np.count_nonzero(masked_gray < 250)) >= min_pixels


def build_color_mask_image(image_bgr: np.ndarray, color_tag: ColorTag) -> np.ndarray:
    """对输入图按 RGB 范围构建二值掩码，并返回 OCR 友好的灰度图。"""
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    lower = np.array(color_tag.rgb_min, dtype=np.uint8)
    upper = np.array(color_tag.rgb_max, dtype=np.uint8)
    mask = cv2.inRange(image_rgb, lower, upper)

    kernel = np.ones((2, 2), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    return cv2.bitwise_not(mask)


def _extract_message_text(content: Any) -> str:
    """兼容 OpenAI 风格返回，提取 message.content 文本。"""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    chunks.append(text)
        return "\n".join(chunks).strip()
    return ""


def _extract_chat_content(data: dict[str, Any]) -> str:
    """从 chat/completions 响应体中提取首条内容。"""
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return _extract_message_text(message.get("content"))


def _normalize_bbox(
    bbox: Any, *, width: int, height: int
) -> Optional[tuple[float, float, float, float]]:
    """将像素或已归一化 bbox 转为相对 [0,1] 的 (x0,y0,x1,y1)。"""
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    # layout_parsing 常见像素坐标；若已是 0~1 则直接裁剪
    if max(abs(x0), abs(y0), abs(x1), abs(y1)) > 1.5:
        x0, x1 = x0 / width, x1 / width
        y0, y1 = y0 / height, y1 / height
    x0 = min(max(x0, 0.0), 1.0)
    y0 = min(max(y0, 0.0), 1.0)
    x1 = min(max(x1, 0.0), 1.0)
    y1 = min(max(y1, 0.0), 1.0)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _extract_layout_parsing_lines(
    data: dict[str, Any], *, width: int, height: int
) -> list[OCRLine]:
    """从 GLM-OCR layout_parsing 响应提取带 bbox 的行。"""
    details = data.get("layout_details", [])
    text_items: list[tuple[float, float, str, Optional[tuple[float, float, float, float]]]] = []
    for page in details:
        if not isinstance(page, list):
            continue
        for elem in page:
            if not isinstance(elem, dict):
                continue
            if elem.get("label") not in {"text", "formula", "table"}:
                continue
            content = str(elem.get("content", "")).strip()
            if not content:
                continue
            if content.startswith("#"):
                content = content.lstrip("#").strip()
            raw_bbox = elem.get("bbox_2d") or elem.get("bbox") or [0, 0, 0, 0]
            norm = _normalize_bbox(raw_bbox, width=width, height=height)
            y = float(raw_bbox[1]) if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 2 else 0.0
            x = float(raw_bbox[0]) if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 1 else 0.0
            text_items.append((y, x, content, norm))

    if text_items:
        text_items.sort(key=lambda item: (item[0], item[1]))
        return [OCRLine(text=item[2], bbox=item[3]) for item in text_items]

    # 回退：仅有 md_results 时按行拆分，无 bbox
    md = str(data.get("md_results", "")).strip()
    if not md:
        return []
    lines: list[OCRLine] = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped:
            lines.append(OCRLine(text=stripped, bbox=None))
    return lines


def _safe_json_loads(raw_text: str) -> Any | None:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _normalize_translation_payload(parsed: Any) -> list[dict[str, str]]:
    """将模型输出归一化为 [{color_tag, translated, source_text?}]。"""
    if parsed is None:
        return []

    if isinstance(parsed, dict):
        if isinstance(parsed.get("results"), list):
            parsed = parsed["results"]
        else:
            parsed = [parsed]

    if not isinstance(parsed, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        color_tag = (
            item.get("color_tag")
            or item.get("label")
            or item.get("tag")
            or "Unknown"
        )
        translated = (
            item.get("translated")
            or item.get("translation")
            or item.get("text")
            or ""
        )
        translated_text = str(translated).strip()
        source_text = str(
            item.get("source_text") or item.get("raw_text") or item.get("source") or ""
        ).strip()
        if translated_text:
            entry = {
                "color_tag": str(color_tag).strip(),
                "translated": translated_text,
            }
            if source_text:
                entry["source_text"] = source_text
            normalized.append(entry)
    return normalized


def _cache_key_for_ocr(source_items: Sequence[OCRResult]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            item.color_tag.label if item.color_tag else "Unknown",
            " ".join(item.raw_text.strip().split()),
        )
        for item in source_items
    )


def _get_enabled_color_palette() -> list[ColorTag]:
    if not OCR_CHANNELS:
        return list(COLOR_PALETTE)
    enabled = {label.lower() for label in OCR_CHANNELS}
    selected = [tag for tag in COLOR_PALETTE if tag.label.lower() in enabled]
    return selected or list(COLOR_PALETTE)


def _iter_source_units(ocr_results: Sequence[OCRResult]) -> list[tuple[OCRResult, OCRLine]]:
    """将通道 OCR 拆成可翻译的行单元；无 lines 时退回整块。"""
    units: list[tuple[OCRResult, OCRLine]] = []
    for item in ocr_results:
        if not item.is_valid or not item.raw_text.strip():
            continue
        if item.lines:
            for line in item.lines:
                if line.text.strip():
                    units.append((item, line))
        else:
            units.append((item, OCRLine(text=item.raw_text.strip(), bbox=None)))
    return units


class OWColorFluentApiClient:
    """`glm-ocr` + `deepseek-v4-flash` 混合快路径客户端。"""

    def __init__(
        self,
        *,
        glm_api_key: str = GLM_API_KEY,
        deepseek_api_key: str = DEEPSEEK_API_KEY,
        glm_url: str = GLM_OCR_URL,
        glm_model: str = GLM_OCR_MODEL,
        deepseek_url: str = DEEPSEEK_URL,
        deepseek_model: str = DEEPSEEK_MODEL,
        timeout_sec: float = HTTP_TIMEOUT_SEC,
        max_concurrent_ocr: int = OCR_MAX_CONCURRENT,
        translation_memory: TranslationMemory | None = None,
    ) -> None:
        self._glm_api_key = glm_api_key
        self._deepseek_api_key = deepseek_api_key
        self._glm_url = glm_url
        self._glm_model = glm_model
        self._deepseek_url = deepseek_url
        self._deepseek_model = deepseek_model
        self._timeout = httpx.Timeout(timeout_sec)
        self._ocr_semaphore = asyncio.Semaphore(max_concurrent_ocr)
        self._client: httpx.AsyncClient | None = None
        self._memory = translation_memory or GLOBAL_TRANSLATION_MEMORY
        self._prefix_warmed = False
        self._last_prefetch_fingerprint: tuple[tuple[str, str], ...] | None = None
        self._last_prefetch_ocr: list[OCRResult] = []
        self._last_prefetch_at: float = 0.0

    async def __aenter__(self) -> "OWColorFluentApiClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def warm_translation_prefix(self) -> bool:
        """预热 DeepSeek 指令前缀缓存（system prompt 落盘），降低首次 F8 TTFT。"""
        if self._prefix_warmed or not self._deepseek_api_key:
            return self._prefix_warmed
        payload = self._build_chat_payload(build_warmup_messages())
        headers = {"Authorization": f"Bearer {self._deepseek_api_key}"}
        try:
            response = await self.client.post(
                self._deepseek_url, headers=headers, json=payload
            )
            response.raise_for_status()
            self._prefix_warmed = True
            return True
        except httpx.HTTPError:
            return False

    def _build_chat_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._deepseek_model,
            "temperature": 0.1,
            "max_tokens": DEEPSEEK_MAX_TOKENS,
            "messages": messages,
        }
        # v4-flash 默认 thinking=enabled，实时字幕必须关掉
        if DEEPSEEK_THINKING_DISABLED:
            payload["thinking"] = {"type": "disabled"}
        return payload

    async def process_multi_channel_ocr(
        self, capture_data: CaptureData
    ) -> List[OCRResult]:
        started = time.perf_counter()
        if not self._glm_api_key:
            return [
                OCRResult(
                    raw_text="",
                    is_valid=False,
                    color_tag=tag,
                    error_msg="GLM_API_KEY 未配置",
                )
                for tag in _get_enabled_color_palette()
            ]

        try:
            image_bgr = decode_base64_image_to_bgr(capture_data.image_base64)
        except Exception as exc:
            return [
                OCRResult(
                    raw_text="",
                    is_valid=False,
                    color_tag=None,
                    error_msg=f"图像解码失败: {exc}",
                )
            ]

        height, width = image_bgr.shape[:2]
        tasks = [
            asyncio.create_task(
                self._run_masked_ocr(
                    image_bgr=image_bgr,
                    color_tag=tag,
                    width=width,
                    height=height,
                )
            )
            for tag in _get_enabled_color_palette()
        ]
        results = list(await asyncio.gather(*tasks))
        logger.info(
            "process_multi_channel_ocr: %.1fms valid=%s/%s",
            _elapsed_ms(started),
            sum(1 for item in results if item.is_valid),
            len(results),
        )
        return results

    async def _run_masked_ocr(
        self,
        *,
        image_bgr: np.ndarray,
        color_tag: ColorTag,
        width: int,
        height: int,
    ) -> OCRResult:
        async with self._ocr_semaphore:
            try:
                masked_gray = build_color_mask_image(image_bgr=image_bgr, color_tag=color_tag)
                if not _mask_has_foreground(masked_gray):
                    return OCRResult(
                        raw_text="",
                        is_valid=False,
                        color_tag=color_tag,
                        error_msg="OCR 无文本输出",
                    )
                masked_bgr = cv2.cvtColor(masked_gray, cv2.COLOR_GRAY2BGR)
                file_data_uri = encode_bgr_image_to_jpeg_data_uri(masked_bgr)
                lines = await self._request_glm_ocr_lines(
                    file_data_uri, width=width, height=height
                )
                cleaned = "\n".join(line.text for line in lines).strip()
                return OCRResult(
                    raw_text=cleaned,
                    is_valid=bool(cleaned),
                    color_tag=color_tag,
                    error_msg=None if cleaned else "OCR 无文本输出",
                    lines=tuple(lines),
                )
            except Exception as exc:
                return OCRResult(
                    raw_text="",
                    is_valid=False,
                    color_tag=color_tag,
                    error_msg=f"OCR 通道失败: {exc}",
                )

    async def _request_glm_ocr_lines(
        self, file_data_uri: str, *, width: int, height: int
    ) -> list[OCRLine]:
        payload = {
            "model": self._glm_model,
            "file": file_data_uri,
        }
        headers = {"Authorization": f"Bearer {self._glm_api_key}"}

        response = await self.client.post(self._glm_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return _extract_layout_parsing_lines(data, width=width, height=height)

    def remember_prefetch_ocr(self, ocr_results: Sequence[OCRResult]) -> None:
        """缓存最近一次后台 OCR，供 F8 热路径复用。"""
        valid = [item for item in ocr_results if item.is_valid and item.raw_text.strip()]
        self._last_prefetch_ocr = list(valid)
        self._last_prefetch_fingerprint = _cache_key_for_ocr(valid) if valid else None
        self._last_prefetch_at = time.monotonic()

    def take_prefetch_ocr_if_fresh(
        self, *, max_age_sec: float = 1.2
    ) -> Optional[list[OCRResult]]:
        """若预取 OCR 仍新鲜则返回副本，否则 None。"""
        if not self._last_prefetch_ocr:
            return None
        if (time.monotonic() - self._last_prefetch_at) > max_age_sec:
            return None
        return list(self._last_prefetch_ocr)

    async def translate_ocr_results(
        self, ocr_results: Sequence[OCRResult]
    ) -> List[TransResult]:
        units = _iter_source_units(ocr_results)
        if not units:
            return []

        # 整包缓存（与旧逻辑兼容）
        channel_items = [item for item in ocr_results if item.is_valid and item.raw_text.strip()]
        cache_key = _cache_key_for_ocr(channel_items)
        cached = _translation_cache.get(cache_key)
        if cached is not None:
            return cached

        results: list[Optional[TransResult]] = [None] * len(units)
        pending_indices: list[int] = []
        pending_ocr: list[OCRResult] = []

        for idx, (channel, line) in enumerate(units):
            hit = self._memory.lookup(line.text)
            if hit is not None:
                source = (
                    "dict"
                    if normalize_chat_text(line.text) in OW_PHRASE_DICT
                    else "memory"
                )
                results[idx] = TransResult(
                    source_text=line.text,
                    translated=hit,
                    color_tag=channel.color_tag,
                    status_code=200,
                    bbox=line.bbox,
                    source=source,
                )
            else:
                pending_indices.append(idx)
                pending_ocr.append(
                    OCRResult(
                        raw_text=line.text,
                        is_valid=True,
                        color_tag=channel.color_tag,
                        lines=(line,),
                    )
                )

        if pending_indices:
            if not self._deepseek_api_key:
                for idx in pending_indices:
                    channel, line = units[idx]
                    results[idx] = TransResult(
                        source_text=line.text,
                        translated="",
                        color_tag=channel.color_tag,
                        status_code=401,
                        bbox=line.bbox,
                        source="llm",
                    )
            else:
                llm_results = await self._request_llm_translations(pending_ocr)
                by_source: dict[str, TransResult] = {}
                for item in llm_results:
                    key = normalize_chat_text(item.source_text)
                    if key:
                        by_source[key] = item
                for pos, idx in enumerate(pending_indices):
                    channel, line = units[idx]
                    key = normalize_chat_text(line.text)
                    matched = by_source.get(key)
                    if matched is None and pos < len(llm_results):
                        matched = llm_results[pos]
                    if matched is None or not matched.translated.strip():
                        results[idx] = TransResult(
                            source_text=line.text,
                            translated=line.text,
                            color_tag=channel.color_tag,
                            status_code=206,
                            bbox=line.bbox,
                            source="passthrough",
                        )
                    else:
                        translated = matched.translated.strip()
                        self._memory.store(line.text, translated)
                        results[idx] = TransResult(
                            source_text=line.text,
                            translated=translated,
                            color_tag=channel.color_tag,
                            status_code=matched.status_code,
                            bbox=line.bbox,
                            source="llm",
                        )

        final_results = [item for item in results if item is not None]
        if any(item.translated.strip() for item in final_results):
            if len(_translation_cache) >= _TRANSLATION_CACHE_MAX:
                _translation_cache.pop(next(iter(_translation_cache)))
            _translation_cache[cache_key] = final_results
        return final_results

    async def _request_llm_translations(
        self, source_items: Sequence[OCRResult]
    ) -> list[TransResult]:
        started = time.perf_counter()
        payload = self._build_chat_payload(build_translation_messages(source_items))
        headers = {"Authorization": f"Bearer {self._deepseek_api_key}"}
        try:
            response = await self.client.post(
                self._deepseek_url, headers=headers, json=payload
            )
            response.raise_for_status()
            content = _extract_chat_content(response.json())
            results = self._merge_translation_results(
                source_items=source_items,
                raw_content=content,
                status_code=response.status_code,
            )
            logger.info(
                "request_llm_translations: %.1fms lines=%s",
                _elapsed_ms(started),
                len(source_items),
            )
            return results
        except httpx.HTTPError:
            logger.exception(
                "request_llm_translations: %.1fms failed lines=%s",
                _elapsed_ms(started),
                len(source_items),
            )
            return [
                TransResult(
                    source_text=item.raw_text,
                    translated="",
                    color_tag=item.color_tag,
                    status_code=503,
                    bbox=item.lines[0].bbox if item.lines else None,
                    source="llm",
                )
                for item in source_items
            ]

    def _merge_translation_results(
        self,
        *,
        source_items: Sequence[OCRResult],
        raw_content: str,
        status_code: int,
    ) -> List[TransResult]:
        parsed = _safe_json_loads(raw_content)
        if parsed is None:
            # 模型偶发包 Markdown fence
            stripped = raw_content.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`")
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                parsed = _safe_json_loads(stripped)

        structured = _normalize_translation_payload(parsed)
        if structured:
            results: list[TransResult] = []
            for idx, item in enumerate(structured):
                label = item["color_tag"]
                tag = COLOR_TAG_MAP.get(label)
                source_text = item.get("source_text", "")
                if not source_text and idx < len(source_items):
                    source_text = source_items[idx].raw_text
                bbox = None
                if idx < len(source_items) and source_items[idx].lines:
                    bbox = source_items[idx].lines[0].bbox
                elif idx < len(source_items):
                    # 整块无行时无 bbox
                    bbox = None
                if tag is None and idx < len(source_items):
                    tag = source_items[idx].color_tag
                results.append(
                    TransResult(
                        source_text=source_text,
                        translated=item["translated"],
                        color_tag=tag,
                        status_code=status_code,
                        bbox=bbox,
                        source="llm",
                    )
                )
            return results

        lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
        if not lines:
            return [
                TransResult(
                    source_text=item.raw_text,
                    translated="",
                    color_tag=item.color_tag,
                    status_code=502,
                    bbox=item.lines[0].bbox if item.lines else None,
                    source="llm",
                )
                for item in source_items
            ]

        merged: list[TransResult] = []
        for idx, source in enumerate(source_items):
            text = lines[idx] if idx < len(lines) else ""
            merged.append(
                TransResult(
                    source_text=source.raw_text,
                    translated=text,
                    color_tag=source.color_tag,
                    status_code=status_code if text else 206,
                    bbox=source.lines[0].bbox if source.lines else None,
                    source="llm",
                )
            )
        return merged


async def process_multi_channel_ocr(capture_data: CaptureData) -> List[OCRResult]:
    """函数式入口：多通道颜色掩码 OCR。"""
    async with OWColorFluentApiClient() as client:
        return await client.process_multi_channel_ocr(capture_data)


async def translate_ocr_results(ocr_results: Sequence[OCRResult]) -> List[TransResult]:
    """函数式入口：翻译并保留颜色语义。"""
    async with OWColorFluentApiClient() as client:
        return await client.translate_ocr_results(ocr_results)


def serialize_ocr_results(ocr_results: Iterable[OCRResult]) -> str:
    """调试辅助：将 OCR 结果序列化为 JSON 字符串。"""
    return json.dumps([asdict(item) for item in ocr_results], ensure_ascii=False, indent=2)
