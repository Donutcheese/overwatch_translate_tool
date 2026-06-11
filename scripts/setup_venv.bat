@echo off
REM OW-Light-Translator — 一键创建 venv 并安装依赖 (Windows)
REM 双击运行，或在项目根目录执行: scripts\setup_venv.bat

cd /d "%~dp0\.."

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_venv.ps1"
if errorlevel 1 (
    echo.
    echo 安装失败，请检查 Python 3.10+ 是否已安装。
    pause
    exit /b 1
)

echo.
pause
