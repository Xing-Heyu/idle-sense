@echo off
chcp 65001 >nul
title Idle-Sense 启动器

:: 激活虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

:: 启动图形界面
python launch_gui.py
pause
