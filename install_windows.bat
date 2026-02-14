@echo off
title Flow Local - Installer
color 0A

echo.
echo  ============================================
echo    FLOW LOCAL - Offline Voice Dictation
echo    Installer for Windows
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/4] Python found.

:: Upgrade pip
echo [2/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install requirements
echo [3/4] Installing packages (this may take a few minutes)...
echo       Downloading Whisper AI model dependencies...
python -m pip install ^
    faster-whisper ^
    sounddevice ^
    numpy ^
    pyperclip ^
    pyautogui ^
    keyboard ^
    Pillow ^
    pystray ^
    --quiet

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed. Try running as Administrator.
    pause
    exit /b 1
)

echo [4/4] Done!
echo.
echo  ============================================
echo    Installation complete!
echo.
echo    To run Flow Local:
echo      python flow_local.py
echo.
echo    Or double-click: run_flow.bat
echo  ============================================
echo.

:: Launcher already included in the zip

echo Launcher created: run_flow.bat
echo.
pause
