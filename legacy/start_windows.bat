@echo off
chcp 65001 >nul
echo ========================================================
echo ⚡ 闲置计算加速器 - Windows启动脚本
echo ========================================================
echo.

echo 📁 项目目录: %CD%
echo.

echo 🚀 启动调度中心...
start "调度中心" cmd /k "cd /d %CD% && python scheduler/simple_server.py"
echo.

echo ⏳ 等待调度中心启动...
timeout /t 5 /nobreak >nul

echo 🚀 启动Windows节点客户端...
start "节点客户端" cmd /k "cd /d %CD% && python node/windows_client.py"
echo.

echo ⏳ 等待节点客户端启动...
timeout /t 3 /nobreak >nul

echo 🚀 启动网页界面...
start "网页界面" cmd /k "cd /d %CD% && streamlit run web_interface.py"
echo.

echo ========================================================
echo 🎉 所有组件启动完成！
echo ========================================================
echo.
echo 📊 服务状态:
echo   • 调度中心: http://localhost:8000
echo   • 网页界面: http://localhost:8501
echo   • 节点客户端: 正在运行
echo.
echo 💡 使用说明:
echo   1. 打开浏览器访问 http://localhost:8501
echo   2. 在网页界面提交计算任务
echo   3. 节点客户端会自动执行任务
echo   4. 在网页界面查看任务结果
echo.
echo 🔧 故障排除:
echo   • 如果节点客户端有问题，检查窗口中的错误信息
echo   • 确保所有依赖已安装: pip install -r requirements.txt
echo.
echo ========================================================
echo.

pause