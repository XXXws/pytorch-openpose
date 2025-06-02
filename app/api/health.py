#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康检查和系统状态API
提供服务健康状态和设备信息查询
"""

from fastapi import APIRouter
import torch
import psutil
import os
from datetime import datetime
import gc
from app.core.performance_service import get_performance_monitor

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
    disk = psutil.disk_usage('/')
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

@router.get("/models")
async def model_status():
    """检查模型文件状态"""
    model_files = [
        "model/body_pose_model.pth",
        "model/hand_pose_model.pth"
    ]
    
    models_info = {}
    for model_file in model_files:
        if os.path.exists(model_file):
            size_mb = round(os.path.getsize(model_file) / (1024 * 1024), 1)
            models_info[os.path.basename(model_file)] = {
                "exists": True,
                "size_mb": size_mb,
                "path": model_file
            }
        else:
            models_info[os.path.basename(model_file)] = {
                "exists": False,
                "size_mb": 0,
                "path": model_file
            }
    
    return {
        "models": models_info,
        "all_models_available": all(info["exists"] for info in models_info.values()),
        "timestamp": datetime.now().isoformat()
    }

@router.post("/gc")
async def garbage_collect():
    """手动触发垃圾回收和GPU内存清理"""
    # Python垃圾回收
    collected = gc.collect()
    
    result = {
        "python_gc_collected": collected,
        "timestamp": datetime.now().isoformat()
    }
    
    # GPU内存清理
    if torch.cuda.is_available():
        before_allocated = torch.cuda.memory_allocated(0)
        before_cached = torch.cuda.memory_reserved(0)
        
        torch.cuda.empty_cache()
        
        after_allocated = torch.cuda.memory_allocated(0)
        after_cached = torch.cuda.memory_reserved(0)
        
        result.update({
            "gpu_memory_before": {
                "allocated_gb": round(before_allocated / 1024**3, 2),
                "cached_gb": round(before_cached / 1024**3, 2)
            },
            "gpu_memory_after": {
                "allocated_gb": round(after_allocated / 1024**3, 2),
                "cached_gb": round(after_cached / 1024**3, 2)
            },
            "gpu_memory_freed": {
                "allocated_gb": round((before_allocated - after_allocated) / 1024**3, 2),
                "cached_gb": round((before_cached - after_cached) / 1024**3, 2)
            }
        })
    
    return result

# 性能监控相关接口
@router.get("/performance/stats")
async def performance_stats():
    """获取性能监控统计"""
    monitor = get_performance_monitor()
    stats = monitor.get_current_stats()
    
    return {
        "performance_stats": stats,
        "monitoring_active": monitor.monitoring,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/performance/start")
async def start_performance_monitoring(interval: float = 1.0):
    """启动性能监控"""
    monitor = get_performance_monitor()
    monitor.start_monitoring(interval)
    
    return {
        "message": "性能监控已启动",
        "interval": interval,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/performance/stop")
async def stop_performance_monitoring():
    """停止性能监控"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring()
    
    return {
        "message": "性能监控已停止",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/performance/baseline")
async def run_baseline_test():
    """运行基准性能测试"""
    monitor = get_performance_monitor()
    results = monitor.run_baseline_test()
    
    return {
        "message": "基准测试完成",
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/performance/report")
async def export_performance_report():
    """导出性能报告"""
    monitor = get_performance_monitor()
    report_file = monitor.export_performance_report()
    
    return {
        "message": "性能报告已生成",
        "report_file": report_file,
        "timestamp": datetime.now().isoformat()
    } 