#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控API
提供系统性能状态查询和建议
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import traceback

from app.core.performance_monitor import get_performance_monitor

router = APIRouter()

@router.get("/performance/status")
async def get_performance_status():
    """获取系统性能状态"""
    try:
        monitor = get_performance_monitor()
        status = monitor.get_performance_status()
        
        return {
            "success": True,
            "performance_status": status,
            "timestamp": status.get('metrics', {}).get('timestamp')
        }
        
    except Exception as e:
        print(f"获取性能状态失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取性能状态失败: {str(e)}")

@router.get("/performance/metrics")
async def get_performance_metrics():
    """获取详细性能指标"""
    try:
        monitor = get_performance_monitor()
        current_metrics = monitor.get_current_metrics()
        average_metrics = monitor.get_average_metrics(duration_seconds=60)
        
        if not current_metrics:
            raise HTTPException(status_code=503, detail="无法获取性能指标")
        
        return {
            "success": True,
            "current_metrics": {
                "cpu_percent": current_metrics.cpu_percent,
                "memory_percent": current_metrics.memory_percent,
                "gpu_memory_used_mb": current_metrics.gpu_memory_used,
                "gpu_memory_total_mb": current_metrics.gpu_memory_total,
                "gpu_memory_percent": (
                    current_metrics.gpu_memory_used / current_metrics.gpu_memory_total * 100
                    if current_metrics.gpu_memory_total > 0 else 0.0
                ),
                "disk_io_read_mbps": current_metrics.disk_io_read,
                "disk_io_write_mbps": current_metrics.disk_io_write,
                "network_io_sent_mb": current_metrics.network_io_sent,
                "network_io_recv_mb": current_metrics.network_io_recv,
                "timestamp": current_metrics.timestamp
            },
            "average_metrics_60s": average_metrics
        }
        
    except Exception as e:
        print(f"获取性能指标失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")

@router.get("/performance/recommendations")
async def get_processing_recommendations():
    """获取视频处理性能建议"""
    try:
        monitor = get_performance_monitor()
        recommendations = monitor.get_processing_recommendations()
        
        return {
            "success": True,
            "recommendations": recommendations
        }
        
    except Exception as e:
        print(f"获取性能建议失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取性能建议失败: {str(e)}")

@router.get("/performance/history")
async def get_performance_history(duration: int = 300):
    """获取性能历史数据"""
    try:
        monitor = get_performance_monitor()
        
        # 限制查询时长
        if duration > 3600:  # 最多1小时
            duration = 3600
        elif duration < 60:  # 最少1分钟
            duration = 60
            
        import time
        current_time = time.time()
        
        # 获取指定时间段内的历史数据
        history_data = []
        for metrics in monitor.metrics_history:
            if current_time - metrics.timestamp <= duration:
                history_data.append({
                    "timestamp": metrics.timestamp,
                    "cpu_percent": metrics.cpu_percent,
                    "memory_percent": metrics.memory_percent,
                    "gpu_memory_percent": (
                        metrics.gpu_memory_used / metrics.gpu_memory_total * 100
                        if metrics.gpu_memory_total > 0 else 0.0
                    ),
                    "disk_io_read_mbps": metrics.disk_io_read,
                    "disk_io_write_mbps": metrics.disk_io_write
                })
        
        return {
            "success": True,
            "duration_seconds": duration,
            "data_points": len(history_data),
            "history": history_data
        }
        
    except Exception as e:
        print(f"获取性能历史失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取性能历史失败: {str(e)}") 