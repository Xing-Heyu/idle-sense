@echo off
chcp 65001 >nul
title Idle-Sense 调度器

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║           Idle-Sense 调度器                                 ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

:: 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo 正在启动调度器...
echo 访问地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
python -m legacy.cli scheduler start --port 8000
