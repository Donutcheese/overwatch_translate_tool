"""项目资源路径解析（开发环境与 PyInstaller 打包环境通用）。"""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """源码运行时为仓库根目录；onefile 打包后为 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def asset_path(*parts: str) -> Path:
    """定位 img/ 等资源文件。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = project_root()
    return base.joinpath(*parts)


def icon_ico_path() -> Path:
    return asset_path("img", "icon.ico")


def icon_png_path() -> Path:
    return asset_path("img", "icon.png")
