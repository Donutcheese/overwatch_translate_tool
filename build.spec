# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 运行 scripts/build.ps1 或 scripts/build.bat。"""

from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "img" / "icon.ico"), "img"),
        (str(ROOT / "img" / "icon.png"), "img"),
    ],
    hiddenimports=[
        "customtkinter",
        "PIL",
        "PIL._tkinter_finder",
        "win32gui",
        "win32api",
        "pywintypes",
        "keyboard",
        "mss",
        "cv2",
        "numpy",
        "httpx",
        "anyio",
        "httpcore",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OW-Color-Fluent-Translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "img" / "icon.ico"),
)
