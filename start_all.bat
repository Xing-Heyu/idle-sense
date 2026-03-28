@echo off
chcp 65001 >nul
echo ========================================
echo   Idle-Sense - Quick Start
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

echo [1/4] Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing dependencies...
    pip install -r requirements.txt
) else (
    echo [2/4] Dependencies OK
)

echo [3/4] Starting scheduler...
start "Scheduler" /min python -m legacy.scheduler.simple_server

echo Waiting for scheduler...
ping -n 6 127.0.0.1 >nul

REM Check if scheduler is running
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Scheduler may have failed to start
    echo You can start manually: python -m legacy.scheduler.simple_server
) else (
    echo [OK] Scheduler running at: http://localhost:8000
)

echo [4/4] Starting Web UI...
echo.
echo ========================================
echo   Started successfully!
echo ========================================
echo.
echo Web UI: http://localhost:8501
echo Scheduler: http://localhost:8000
echo Press Ctrl+C to stop
echo.

streamlit run src/presentation/streamlit/app.py
