@echo off
REM OW-Light-Translator - create venv and install dependencies (Windows)
REM Double click this file, or run from project root: scripts\setup_venv.bat

cd /d "%~dp0\.."

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_venv.ps1"
if errorlevel 1 (
    echo.
    echo Setup failed. Please check Python 3.10+ is installed.
    pause
    exit /b 1
)

echo.
pause
