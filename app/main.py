#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI主应用程序
整合所有API路由和服务
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import uvicorn
import os
import sys
import traceback

from app.logger import setup_logging
from app.config import settings

setup_logging()
logger = logging.getLogger(__name__)

# 设置UTF-8编码，避免Windows下的GBK编码问题
if sys.platform == "win32":
    import os
    
    # 设置环境变量强制UTF-8编码（仅在未设置时设置）
    if 'PYTHONIOENCODING' not in os.environ:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

# 确保项目根目录在Python路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 获取项目根目录
if project_root not in sys.path:
    sys.path.insert(0, project_root)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("FastAPI应用启动中...")
    
    # 创建必要的目录
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.result_dir, exist_ok=True)
    os.makedirs(settings.image_dir, exist_ok=True)
    logger.info("目录创建完成")
    
    # 启动性能监控
    try:
        from app.core.performance_monitor import start_performance_monitoring
        start_performance_monitoring()
        logger.info("性能监控启动成功")
    except Exception as e:
        logger.error(f"性能监控启动失败: {e}")
    
    logger.info("FastAPI应用启动完成")
    
    yield
    
    # 关闭时执行
    try:
        from app.core.performance_monitor import stop_performance_monitoring
        stop_performance_monitoring()
        logger.info("性能监控已停止")
    except Exception as e:
        logger.error(f"性能监控停止失败: {e}")
    
    logger.info("FastAPI应用关闭")

# 创建FastAPI应用
app = FastAPI(
    title="PyTorch OpenPose Web API",
    description="基于PyTorch的OpenPose姿态检测Web服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加静态文件服务
if not os.path.exists(settings.upload_dir):
    os.makedirs(settings.upload_dir)
if not os.path.exists(settings.result_dir):
    os.makedirs(settings.result_dir)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/results", StaticFiles(directory=settings.result_dir), name="results")

# 导入API路由
try:
    from app.api import detection, video, health, realtime, performance
    
    # 注册路由
    app.include_router(detection.router, prefix="/api", tags=["检测"])
    app.include_router(video.router, tags=["视频处理"])  # video.py中已有prefix="/api/video"
    app.include_router(health.router, prefix="/api", tags=["健康检查"])
    app.include_router(realtime.router, prefix="/api", tags=["实时检测"])
    app.include_router(performance.router, prefix="/api", tags=["性能监控"])
    
    logger.info("所有API路由加载成功")
    
except Exception as e:
    logger.exception(f"API路由加载失败: {e}")

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "PyTorch OpenPose Web API",
        "version": "1.0.0",
        "status": "运行中",
        "endpoints": {
            "健康检查": "/api/health",
            "设备信息": "/api/device", 
            "系统信息": "/api/system",
            "图像检测": "/api/detect/image",
            "文件上传检测": "/api/detect/upload",
            "视频上传": "/api/video/upload",
            "视频任务状态": "/api/video/task/{task_id}",
            "实时检测": "/api/ws/realtime/{client_id}"
        }
    }

# 错误处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.exception(f"全局异常: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "服务器内部错误",
            "detail": str(exc),
            "type": type(exc).__name__
        }
    )

if __name__ == "__main__":
    logger.info("启动PyTorch OpenPose Web服务")
    logger.info("访问地址: http://localhost:8000")
    logger.info("API文档: http://localhost:8000/docs")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
