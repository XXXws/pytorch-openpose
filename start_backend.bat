@echo off
echo 启动PyTorch OpenPose后端服务...
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：Python未安装或不在PATH中
    pause
    exit /b 1
)

REM 切换到项目根目录
cd /d "%~dp0"

REM 启动后端服务
echo 正在启动后端服务...
echo 访问地址: http://localhost:8001
echo API文档: http://localhost:8001/docs
echo.
echo 按 Ctrl+C 停止服务
echo.

python -m app.main

pause
