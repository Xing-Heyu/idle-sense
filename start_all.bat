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

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    echo [1/5] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [1/5] Using system Python...
)

echo [2/5] Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [3/5] Installing dependencies...
    pip install -r requirements.txt
) else (
    echo [3/5] Dependencies OK
)

echo [4/5] Starting scheduler...
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

echo [5/5] Starting Web UI...
echo.
echo ========================================
echo   Started successfully!
echo ========================================
echo.
echo Web UI: http://localhost:8501
echo Scheduler: http://localhost:8000
echo Press Ctrl+C to stop
echo.

REM Set PYTHONPATH to project root for module imports
set PYTHONPATH=%~dp0
streamlit run src/presentation/streamlit/app.py
