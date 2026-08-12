@echo off
setlocal EnableDelayedExpansion

title BindCraft Launcher
color 0B

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║         BindCraft — AMBER MD Platform        ║
echo  ║   Crafting protein-ligand MD workflows       ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Move to repo root
cd /d "%~dp0"

:: Create .env from example if missing
if not exist ".env" (
    echo  [INFO] Creating .env from .env.example ...
    copy ".env.example" ".env" >nul
)

:: Create virtual environment if missing
if not exist "venv\Scripts\activate.bat" (
    echo  [INFO] Creating virtual environment ...
    python -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install / upgrade dependencies
echo  [INFO] Checking dependencies ...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

:: Create projects directory if missing
if not exist "projects" mkdir projects

:: Run BindCraft Desktop GUI
python gui.py

pause
