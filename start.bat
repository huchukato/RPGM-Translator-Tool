@echo off
setlocal

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [RPGM-Translator] uv not found. Installing...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [RPGM-Translator] ERROR: uv installation failed.
    pause
    exit /b 1
)

echo [RPGM-Translator] Starting...
cd /d "%~dp0"
set UV_LINK_MODE=copy
uv run rpgm_tool.py %*
pause
