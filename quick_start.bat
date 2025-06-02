@echo off
echo Starting PyTorch OpenPose Demo...

start "Backend" cmd /k "cd /d D:\pytorch-openpose-master && python -m uvicorn app.main:app --reload --port 8000"
start "Frontend" cmd /k "cd /d D:\pytorch-openpose-master\frontend && npm run dev"

echo Services started!
echo Backend: http://localhost:8000  
echo Frontend: http://localhost:3000