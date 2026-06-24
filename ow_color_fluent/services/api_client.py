"""异步 API 客户端：内存截图、多通道 OCR、翻译聚合。"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import asdict
from typing import Any, Iterable, List, Sequence

import cv2
import httpx
import mss
import numpy as np

from ..core.config import (
    COLOR_PALETTE,
    COLOR_TAG_MAP,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_URL,
    GLM_API_KEY,
    GLM_OCR_MODEL,
    GLM_OCR_URL,
    HTTP_TIMEOUT_SEC,
    OCR_CHANNELS,
    OCR_MAX_CONCURRENT,
    CaptureData,
    ColorTag,
    OCRResult,
    TransResult,
)
from ..core.prompts import build_translation_messages


_TRANSLATION_CACHE_MAX = 256
_translation_cache: dict[tuple[tuple[str, str], ...], list[TransResult]] = {}


def capture_region_to_base64(region: dict[str, int]) -> CaptureData:
    """使用 `mss` 捕获指定区域并转为 PNG Base64（纯内存）。"""
    with mss.mss() as sct:
        shot = sct.grab(region)
        bgra_frame = np.array(shot, dtype=np.uint8)

    bgr_frame = cv2.cvtColor(bgra_frame, cv2.COLOR_BGRA2BGR)
    ok, encoded = cv2.imencode(".png", bgr_frame)
    if not ok:
        raise RuntimeError("截图编码失败：无法将内存图像编码为 PNG。")

    image_base64 = base64.b64encode(encoded.tobytes()).decode("utf-8")
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


def _extract_layout_parsing_text(data: dict[str, Any]) -> str:
    """从 GLM-OCR layout_parsing 响应中提取纯文本。"""
    md = str(data.get("md_results", "")).strip()
    if md:
        lines: list[str] = []
        for line in md.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                stripped = stripped.lstrip("#").strip()
            if stripped:
                lines.append(stripped)
        if lines:
            return "\n".join(lines)

    details = data.get("layout_details", [])
    text_items: list[tuple[float, float, str]] = []
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
            bbox = elem.get("bbox_2d") or [0, 0, 0, 0]
            y = float(bbox[1]) if len(bbox) >= 2 else 0.0
            x = float(bbox[0]) if len(bbox) >= 1 else 0.0
            text_items.append((y, x, content))

    text_items.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(item[2] for item in text_items).strip()


def _safe_json_loads(raw_text: str) -> Any | None:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _normalize_translation_payload(parsed: Any) -> list[dict[str, str]]:
    """将模型输出归一化为 [{color_tag, translated}]。"""
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
        if translated_text:
            normalized.append(
                {"color_tag": str(color_tag).strip(), "translated": translated_text}
            )
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


class OWColorFluentApiClient:
    """`glm-ocr` 与 `deepseek-chat` 的异步调用封装。"""

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

    async def process_multi_channel_ocr(
        self, capture_data: CaptureData
    ) -> List[OCRResult]:
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

        tasks = [
            asyncio.create_task(self._run_masked_ocr(image_bgr=image_bgr, color_tag=tag))
            for tag in _get_enabled_color_palette()
        ]
        return list(await asyncio.gather(*tasks))

    async def _run_masked_ocr(self, *, image_bgr: np.ndarray, color_tag: ColorTag) -> OCRResult:
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
                text = await self._request_glm_ocr(file_data_uri)
                cleaned = text.strip()
                return OCRResult(
                    raw_text=cleaned,
                    is_valid=bool(cleaned),
                    color_tag=color_tag,
                    error_msg=None if cleaned else "OCR 无文本输出",
                )
            except Exception as exc:
                return OCRResult(
                    raw_text="",
                    is_valid=False,
                    color_tag=color_tag,
                    error_msg=f"OCR 通道失败: {exc}",
                )

    async def _request_glm_ocr(self, file_data_uri: str) -> str:
        payload = {
            "model": self._glm_model,
            "file": file_data_uri,
        }
        headers = {"Authorization": f"Bearer {self._glm_api_key}"}

        response = await self.client.post(self._glm_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return _extract_layout_parsing_text(data)

    async def translate_ocr_results(
        self, ocr_results: Sequence[OCRResult]
    ) -> List[TransResult]:
        valid_items = [item for item in ocr_results if item.is_valid and item.raw_text.strip()]
        if not valid_items:
            return []
        cache_key = _cache_key_for_ocr(valid_items)
        cached = _translation_cache.get(cache_key)
        if cached is not None:
            return cached

        if not self._deepseek_api_key:
            return [
                TransResult(
                    source_text=item.raw_text,
                    translated="",
                    color_tag=item.color_tag,
                    status_code=401,
                )
                for item in valid_items
            ]

        payload = {
            "model": self._deepseek_model,
            "temperature": 0.1,
            "messages": build_translation_messages(valid_items),
        }
        headers = {"Authorization": f"Bearer {self._deepseek_api_key}"}

        try:
            response = await self.client.post(self._deepseek_url, headers=headers, json=payload)
            response.raise_for_status()
            content = _extract_chat_content(response.json())
            results = self._merge_translation_results(
                source_items=valid_items,
                raw_content=content,
                status_code=response.status_code,
            )
            if any(item.translated.strip() for item in results):
                if len(_translation_cache) >= _TRANSLATION_CACHE_MAX:
                    _translation_cache.pop(next(iter(_translation_cache)))
                _translation_cache[cache_key] = results
            return results
        except httpx.HTTPError:
            return [
                TransResult(
                    source_text=item.raw_text,
                    translated="",
                    color_tag=item.color_tag,
                    status_code=503,
                )
                for item in valid_items
            ]

    def _merge_translation_results(
        self,
        *,
        source_items: Sequence[OCRResult],
        raw_content: str,
        status_code: int,
    ) -> List[TransResult]:
        parsed = _safe_json_loads(raw_content)
        structured = _normalize_translation_payload(parsed)
        if structured:
            results: list[TransResult] = []
            for item in structured:
                label = item["color_tag"]
                tag = COLOR_TAG_MAP.get(label)
                results.append(
                    TransResult(
                        source_text="",
                        translated=item["translated"],
                        color_tag=tag,
                        status_code=status_code,
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
