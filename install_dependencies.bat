@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ================================================================
echo           PyTorch OpenPose GPU依赖自动安装脚本
echo ================================================================
echo.

:: 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [✓] 检测到管理员权限
) else (
    echo [!] 建议以管理员权限运行此脚本
)
echo.

:: 第1步：检查Python
echo [第1步] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] 错误: Python未安装或不在PATH中
    echo     请先安装Python 3.7-3.11版本
    echo     下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [✓] Python版本: !PYTHON_VERSION!
)
echo.

:: 第2步：检查pip
echo [第2步] 检查pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] pip未正确安装
    pause
    exit /b 1
) else (
    echo [✓] pip可用
)
echo.

:: 第3步：升级pip
echo [第3步] 升级pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [!] pip升级失败，但继续安装...
) else (
    echo [✓] pip升级完成
)
echo.

:: 第4步：检查GPU环境
echo [第4步] 检查GPU环境...
nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 未检测到NVIDIA GPU或驱动，将安装CPU版本PyTorch
    set INSTALL_GPU=false
) else (
    echo [✓] 检测到NVIDIA GPU
    nvidia-smi | findstr /C:"CUDA Version"
    set INSTALL_GPU=true
)
echo.

:: 第5步：安装基础依赖
echo [第5步] 安装基础依赖...
echo     安装numpy...
pip install "numpy>=1.19.0"
if %errorlevel% neq 0 goto :install_error

echo     安装matplotlib...
pip install "matplotlib>=3.3.0"
if %errorlevel% neq 0 goto :install_error

echo     安装opencv-python...
pip install "opencv-python>=4.5.0"
if %errorlevel% neq 0 goto :install_error

echo     安装scipy...
pip install "scipy>=1.6.0"
if %errorlevel% neq 0 goto :install_error

echo     安装scikit-image...
pip install "scikit-image>=0.17.0"
if %errorlevel% neq 0 goto :install_error

echo     安装tqdm...
pip install "tqdm>=4.60.0"
if %errorlevel% neq 0 goto :install_error

echo [✓] 基础依赖安装完成
echo.

:: 第6步：安装PyTorch
echo [第6步] 安装PyTorch...
if "%INSTALL_GPU%"=="true" (
    echo     安装GPU版本PyTorch CUDA 11.8...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    if %errorlevel% neq 0 (
        echo [!] GPU版本安装失败，尝试默认版本...
        pip install torch torchvision torchaudio
        if %errorlevel% neq 0 goto :install_error
    )
) else (
    echo     安装CPU版本PyTorch...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    if %errorlevel% neq 0 goto :install_error
)
echo [✓] PyTorch安装完成
echo.

:: 第7步：验证安装
echo [第7步] 验证安装...
echo     验证基础依赖...
python -c "import numpy, cv2, scipy, matplotlib, skimage; print('基础依赖导入成功')" 2>nul
if %errorlevel% neq 0 (
    echo [✗] 基础依赖验证失败
    goto :install_error
) else (
    echo [✓] 基础依赖验证成功
)

echo     验证PyTorch...
python -c "import torch; print(f'PyTorch版本: {torch.__version__}')" 2>nul
if %errorlevel% neq 0 (
    echo [✗] PyTorch验证失败
    goto :install_error
) else (
    echo [✓] PyTorch验证成功
)

echo     检查CUDA支持...
python -c "import torch; print(f'CUDA可用: {torch.cuda.is_available()}'); print(f'GPU设备: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"无GPU\"}')" 2>nul
echo.

:: 第8步：运行快速验证 (如果模型文件存在)
echo [第8步] 检查项目文件...
if exist "quick_start_gpu.py" (
    if exist "model\body_pose_model.pth" (
        if exist "model\hand_pose_model.pth" (
            echo [✓] 检测到模型文件，运行快速验证...
            python quick_start_gpu.py
        ) else (
            echo [!] 缺少手部检测模型: model\hand_pose_model.pth
        )
    ) else (
        echo [!] 缺少人体检测模型: model\body_pose_model.pth
    )
) else (
    echo [!] 快速验证脚本不存在
)
echo.

:: 安装成功
echo ================================================================
echo                        安装完成！
echo ================================================================
echo.
echo [✓] 所有依赖已成功安装
echo.
echo 下一步操作:
echo 1. 确保模型文件位于 model/ 目录下：
echo    - model/body_pose_model.pth
echo    - model/hand_pose_model.pth
echo.
echo 2. 运行验证命令：
echo    python quick_start_gpu.py     (快速验证)
echo    python test_gpu.py           (完整测试)
echo    python demo.py               (图像检测演示)
echo    python demo_camera.py        (实时摄像头检测)
echo.
echo 3. 如遇问题，请参考 "安装指南.md" 文档
echo.
pause
exit /b 0

:install_error
echo.
echo ================================================================
echo                        安装失败！
echo ================================================================
echo.
echo [✗] 依赖安装过程中出现错误
echo.
echo 可能的解决方案：
echo 1. 检查网络连接
echo 2. 以管理员权限重新运行
echo 3. 使用国内镜像源：
echo    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
echo 4. 手动执行安装命令（参考安装指南.md）
echo.
echo 如需技术支持，请保存以上错误信息
echo.
pause
exit /b 1 