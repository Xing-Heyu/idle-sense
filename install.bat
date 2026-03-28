@echo off
chcp 65001 >nul
title Idle-Sense 一键安装

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║           Idle-Sense 分布式算力共享平台                      ║
echo ║                    一键安装程序                              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

:: 检查 Python
echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，正在打开下载页面...
    echo 请下载 Python 3.9 或更高版本并安装
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo ✅ Python %PYVER% 已安装

:: 创建虚拟环境
echo.
echo [2/4] 创建虚拟环境...
if exist venv (
    echo ✅ 虚拟环境已存在
) else (
    python -m venv venv
    echo ✅ 虚拟环境创建成功
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
echo.
echo [3/4] 安装依赖包...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo ✅ 核心依赖安装成功

:: 安装可选依赖
echo.
echo [4/4] 安装可选组件...
pip install wasmtime -q 2>nul
echo ✅ WASM 沙箱支持已安装

:: 检查 Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ℹ️  Docker 未安装，如需容器沙箱请手动安装 Docker Desktop
) else (
    echo ✅ Docker 已安装
)

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                    安装完成！                               ║
echo ╠════════════════════════════════════════════════════════════╣
echo ║  启动方式：                                                 ║
echo ║  1. 双击 start.bat 启动图形界面                             ║
echo ║  2. 双击 start_scheduler.bat 启动调度器                    ║
echo ║  3. 双击 start_node.bat 启动节点客户端                      ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
pause
