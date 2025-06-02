@echo off
title PyTorch OpenPose Web System Demo
cls

REM 设置UTF-8编码环境变量，解决Windows GBK编码问题
set PYTHONIOENCODING=utf-8
chcp 65001 >nul 2>&1

echo ==========================================
echo  PyTorch OpenPose Web System Demo
echo ==========================================
echo.

echo Starting backend service...
start "Backend-API" cmd /k "cd /d D:\pytorch-openpose-master && echo Starting PyTorch OpenPose Backend... && set PYTHONIOENCODING=utf-8 && echo Checking Python modules... && python -c "import fastapi, uvicorn; print('Required modules available')" && echo Starting server on port 8001... && python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

echo Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo Checking backend health...
powershell -Command "try { $response = Invoke-RestMethod -Uri 'http://localhost:8001/api/health' -TimeoutSec 10; Write-Host 'Backend health check: OK' -ForegroundColor Green } catch { Write-Host 'Backend health check: Failed (this is normal during startup)' -ForegroundColor Yellow }"

echo Starting frontend service...
start "Frontend-Dev" cmd /k "cd /d D:\pytorch-openpose-master\frontend && echo Starting Frontend Development Server... && npm run dev"

echo.
echo ==========================================
echo   Services Started Successfully!
echo ==========================================
echo.
echo   Backend API:      http://localhost:8001
echo   Frontend App:     http://localhost:3000 (or next available port)
echo   API Documentation: http://localhost:8001/docs
echo   Performance Monitor: http://localhost:8001/api/performance/status
echo.
echo   IMPORTANT NOTES:
echo   - Backend runs on port 8001 (consistent across all startup methods)
echo   - If port 3000 is occupied, Vite will automatically
echo     use the next available port (e.g., 3001, 3002, etc.)
echo   - Check the Frontend-Dev window for the actual URL
echo   - Both services are running in separate windows
echo   - CORS has been configured for cross-origin requests
echo   - Video playback should work correctly across different ports
echo   - Performance monitoring is automatically enabled
echo.
echo   TROUBLESHOOTING:
echo   - Ensure Python 3.8+ and Node.js are properly installed
echo   - If video playback fails, ensure both services use 'localhost'
echo   - Check browser console for any CORS or network errors
echo   - Monitor system performance at /api/performance/status
echo   - Restart services if you encounter persistent issues
echo.
echo   You can safely close this launcher window.
echo.
echo   Press any key to close this window...
pause >nul