#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的健康检查API
"""

from fastapi import APIRouter
import torch
import psutil
import os
from datetime import datetime
import gc

router = APIRouter()

@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "service": "PyTorch OpenPose Web API",
        "timestamp": datetime.now().isoformat(),
        "uptime": "active"
    }

@router.get("/device")
async def device_info():
    """获取计算设备信息"""
    device_info = {
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device_type": "GPU" if torch.cuda.is_available() else "CPU",
        "timestamp": datetime.now().isoformat()
    }
    
    if torch.cuda.is_available():
        device_info.update({
            "cuda_version": torch.version.cuda,
            "gpu_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory": {
                "allocated_gb": round(torch.cuda.memory_allocated(0) / 1024**3, 2),
                "cached_gb": round(torch.cuda.memory_reserved(0) / 1024**3, 2),
                "total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
            }
        })
    
    return device_info

@router.get("/system")
async def system_info():
    """获取系统资源信息"""
    # CPU信息
    cpu_info = {
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
    }
    
    # 内存信息
    memory = psutil.virtual_memory()
    memory_info = {
        "total_gb": round(memory.total / 1024**3, 2),
        "available_gb": round(memory.available / 1024**3, 2),
        "used_gb": round(memory.used / 1024**3, 2),
        "percent": memory.percent
    }
    
    # 磁盘信息
    try:
        disk = psutil.disk_usage('C:')  # Windows系统使用C盘
    except:
        disk = psutil.disk_usage('/')   # 备用方案
        
    disk_info = {
        "total_gb": round(disk.total / 1024**3, 2),
        "used_gb": round(disk.used / 1024**3, 2),
        "free_gb": round(disk.free / 1024**3, 2),
        "percent": round((disk.used / disk.total) * 100, 2)
    }
    
    return {
        "cpu": cpu_info,
        "memory": memory_info,
        "disk": disk_info,
        "timestamp": datetime.now().isoformat()
    } 