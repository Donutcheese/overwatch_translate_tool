"""将 img/icon.png 转为 Windows 可用的 img/icon.ico（多尺寸）。"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "缺少 Pillow。请先运行: pip install Pillow\n"
        "然后执行: python scripts/generate_icon.py"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
PNG_PATH = ROOT / "img" / "icon.png"
ICO_PATH = ROOT / "img" / "icon.ico"

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def generate_icon() -> Path:
    if not PNG_PATH.is_file():
        raise FileNotFoundError(f"未找到源图标: {PNG_PATH}")

    with Image.open(PNG_PATH) as img:
        rgba = img.convert("RGBA")
        rgba.save(ICO_PATH, format="ICO", sizes=ICO_SIZES)

    print(f"Generated: {ICO_PATH}")
    return ICO_PATH


if __name__ == "__main__":
    generate_icon()
