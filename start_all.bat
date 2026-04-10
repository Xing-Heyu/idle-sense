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

REM ============================================
REM Step 1: Check and activate virtual environment
REM ============================================
set USE_VENV=0
if exist venv\Scripts\activate.bat (
    echo [1/5] Virtual environment found, activating...
    call venv\Scripts\activate.bat
    set USE_VENV=1
) else (
    echo [1/5] No virtual environment found, using system Python...
)

REM ============================================
REM Step 2: Check if key dependencies are installed
REM ============================================
echo [2/5] Checking dependencies...

REM Check streamlit
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [WARN] streamlit not found
    set DEPS_OK=0
) else (
    set DEPS_OK=1
)

REM Check pydantic-settings (required for config.settings)
pip show pydantic-settings >nul 2>&1
if errorlevel 1 (
    echo [WARN] pydantic-settings not found
    set DEPS_OK=0
)

REM ============================================
REM Step 3: Handle missing dependencies
REM ============================================
if "%DEPS_OK%"=="0" (
    if "%USE_VENV%"=="1" (
        echo.
        echo [ERROR] Virtual environment exists but dependencies are missing.
        echo [INFO] Please run: install.bat
        echo [INFO] Or run: venv\Scripts\pip install -r requirements.txt
        pause
        exit /b 1
    ) else (
        echo.
        echo [WARN] Dependencies not found in system Python.
        echo [INFO] You can either:
        echo   1. Run install.bat to create a virtual environment
        echo   2. Install dependencies to system Python: pip install -r requirements.txt
        echo.
        echo [INFO] Attempting to install dependencies to system Python...
        echo [3/5] Installing dependencies...
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies. Please run install.bat manually.
            pause
            exit /b 1
        )
        echo [OK] Dependencies installed successfully
    )
) else (
    echo [3/5] Dependencies OK
)

REM ============================================
REM Step 4: Start scheduler
REM ============================================
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

REM ============================================
REM Step 5: Start Web UI
REM ============================================
echo [5/5] Starting Web UI...
echo.
echo ========================================
echo   Started successfully!
echo ========================================
echo.
if "%USE_VENV%"=="1" (
    echo Environment: Virtual Environment (venv)
) else (
    echo Environment: System Python
)
echo.
echo Web UI: http://localhost:8501
echo Scheduler: http://localhost:8000
echo Press Ctrl+C to stop
echo.

python -m streamlit run src/presentation/streamlit/app.py
