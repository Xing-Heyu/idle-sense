@echo off
chcp 65001 >nul
title Idle-Sense 启动器

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║        Idle-Sense - 生产级分布式算力共享平台               ║
echo ║        Production-Grade Distributed Computing Platform     ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

echo Features:
echo   - LAN: Multicast discovery (instant)
echo   - WAN: DHT discovery + STUN traversal (20-60s)
echo   - Legacy Modules: Health Check, Distributed Lock, Retry, Monitoring
echo   - Zero configuration, fully automatic
echo   - Completely free, no paid services
echo.

REM Check and activate virtual environment
if exist venv\Scripts\activate.bat (
    echo [1/2] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [1/2] Using system Python...
)

echo [2/2] Starting...
echo.

python start.py

pause
