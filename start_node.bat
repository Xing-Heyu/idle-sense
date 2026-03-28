@echo off
chcp 65001 >nul
title Idle-Sense 节点客户端

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║           Idle-Sense 节点客户端                             ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

:: 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

set /p SCHEDULER_URL="请输入调度器地址 (默认 http://localhost:8000): "
if "%SCHEDULER_URL%"=="" set SCHEDULER_URL=http://localhost:8000

echo.
echo 正在连接调度器: %SCHEDULER_URL%
echo 按 Ctrl+C 停止
echo.
python -m legacy.cli node start --scheduler-url %SCHEDULER_URL%
