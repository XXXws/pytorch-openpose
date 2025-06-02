#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块
监控系统资源使用情况，为视频处理提供自适应调节
"""

import asyncio
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

# 尝试导入psutil，如果不可用则使用模拟数据
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("警告: psutil不可用，性能监控将使用模拟数据")

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    cpu_percent: float
    memory_percent: float
    gpu_memory_used: float
    gpu_memory_total: float
    disk_io_read: float
    disk_io_write: float
    network_io_sent: float
    network_io_recv: float
    timestamp: float

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics_history = []
        self.max_history_size = 60  # 保留60个历史记录（约1分钟）
        self.monitoring = False
        self.monitor_task = None
        
        # 性能阈值配置
        self.thresholds = {
            'cpu_high': 80.0,      # CPU使用率高阈值
            'cpu_critical': 95.0,   # CPU使用率临界阈值
            'memory_high': 75.0,    # 内存使用率高阈值
            'memory_critical': 90.0, # 内存使用率临界阈值
            'gpu_memory_high': 80.0, # GPU内存使用率高阈值
            'gpu_memory_critical': 95.0 # GPU内存使用率临界阈值
        }
        
        # 初始化基准值
        self._baseline_metrics = None
        self._last_io_counters = None
        
    def start_monitoring(self, interval: float = 1.0):
        """开始性能监控"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        print(f"性能监控已启动，监控间隔: {interval}秒")
        
    def stop_monitoring(self):
        """停止性能监控"""
        if not self.monitoring:
            return
            
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
        print("性能监控已停止")
        
    async def _monitor_loop(self, interval: float):
        """监控循环"""
        try:
            while self.monitoring:
                metrics = self._collect_metrics()
                if metrics:
                    self._add_metrics(metrics)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"性能监控错误: {e}")
            
    def _collect_metrics(self) -> Optional[PerformanceMetrics]:
        """收集性能指标"""
        try:
            # CPU和内存使用率
            if PSUTIL_AVAILABLE:
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
            else:
                # 使用模拟数据
                cpu_percent = 50.0  # 模拟50%CPU使用率
                memory_percent = 60.0  # 模拟60%内存使用率
            
            # GPU内存使用率（如果可用）
            gpu_memory_used = 0.0
            gpu_memory_total = 0.0
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # 使用第一个GPU
                    gpu_memory_used = gpu.memoryUsed
                    gpu_memory_total = gpu.memoryTotal
            except ImportError:
                # GPUtil不可用，使用nvidia-ml-py3
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_used = info.used / 1024 / 1024  # 转换为MB
                    gpu_memory_total = info.total / 1024 / 1024
                except:
                    pass
            
            # 磁盘I/O
            disk_io_read = 0.0
            disk_io_write = 0.0
            network_io_sent = 0.0
            network_io_recv = 0.0
            
            if PSUTIL_AVAILABLE:
                disk_io = psutil.disk_io_counters()
                
                if disk_io and self._last_io_counters:
                    time_delta = time.time() - self._last_io_counters['timestamp']
                    if time_delta > 0:
                        disk_io_read = (disk_io.read_bytes - self._last_io_counters['read_bytes']) / time_delta / 1024 / 1024  # MB/s
                        disk_io_write = (disk_io.write_bytes - self._last_io_counters['write_bytes']) / time_delta / 1024 / 1024  # MB/s
                
                if disk_io:
                    self._last_io_counters = {
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'timestamp': time.time()
                    }
                
                # 网络I/O
                net_io = psutil.net_io_counters()
                network_io_sent = net_io.bytes_sent / 1024 / 1024 if net_io else 0.0  # MB
                network_io_recv = net_io.bytes_recv / 1024 / 1024 if net_io else 0.0  # MB
            else:
                # 使用模拟数据
                disk_io_read = 10.0  # 模拟10MB/s读取
                disk_io_write = 5.0  # 模拟5MB/s写入
                network_io_sent = 100.0  # 模拟100MB发送
                network_io_recv = 200.0  # 模拟200MB接收
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                gpu_memory_used=gpu_memory_used,
                gpu_memory_total=gpu_memory_total,
                disk_io_read=disk_io_read,
                disk_io_write=disk_io_write,
                network_io_sent=network_io_sent,
                network_io_recv=network_io_recv,
                timestamp=time.time()
            )
            
        except Exception as e:
            print(f"收集性能指标失败: {e}")
            return None
            
    def _add_metrics(self, metrics: PerformanceMetrics):
        """添加性能指标到历史记录"""
        self.metrics_history.append(metrics)
        
        # 保持历史记录大小
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
            
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标"""
        if not self.metrics_history:
            return self._collect_metrics()
        return self.metrics_history[-1]
        
    def get_average_metrics(self, duration_seconds: int = 30) -> Optional[Dict[str, float]]:
        """获取指定时间段内的平均性能指标"""
        if not self.metrics_history:
            return None
            
        current_time = time.time()
        relevant_metrics = [
            m for m in self.metrics_history 
            if current_time - m.timestamp <= duration_seconds
        ]
        
        if not relevant_metrics:
            return None
            
        return {
            'cpu_percent': sum(m.cpu_percent for m in relevant_metrics) / len(relevant_metrics),
            'memory_percent': sum(m.memory_percent for m in relevant_metrics) / len(relevant_metrics),
            'gpu_memory_percent': (
                sum(m.gpu_memory_used / m.gpu_memory_total * 100 for m in relevant_metrics if m.gpu_memory_total > 0) 
                / len([m for m in relevant_metrics if m.gpu_memory_total > 0])
                if any(m.gpu_memory_total > 0 for m in relevant_metrics) else 0.0
            ),
            'disk_io_read': sum(m.disk_io_read for m in relevant_metrics) / len(relevant_metrics),
            'disk_io_write': sum(m.disk_io_write for m in relevant_metrics) / len(relevant_metrics)
        }
        
    def get_performance_status(self) -> Dict[str, Any]:
        """获取性能状态评估"""
        current = self.get_current_metrics()
        if not current:
            return {'status': 'unknown', 'message': '无法获取性能数据'}
            
        # 计算GPU内存使用率
        gpu_memory_percent = (
            current.gpu_memory_used / current.gpu_memory_total * 100 
            if current.gpu_memory_total > 0 else 0.0
        )
        
        # 评估状态
        issues = []
        recommendations = []
        
        # CPU检查
        if current.cpu_percent >= self.thresholds['cpu_critical']:
            issues.append(f"CPU使用率过高: {current.cpu_percent:.1f}%")
            recommendations.append("建议暂停新的视频处理任务")
        elif current.cpu_percent >= self.thresholds['cpu_high']:
            issues.append(f"CPU使用率较高: {current.cpu_percent:.1f}%")
            recommendations.append("建议减少并发处理任务")
            
        # 内存检查
        if current.memory_percent >= self.thresholds['memory_critical']:
            issues.append(f"内存使用率过高: {current.memory_percent:.1f}%")
            recommendations.append("建议释放内存或重启服务")
        elif current.memory_percent >= self.thresholds['memory_high']:
            issues.append(f"内存使用率较高: {current.memory_percent:.1f}%")
            recommendations.append("建议清理缓存")
            
        # GPU内存检查
        if gpu_memory_percent >= self.thresholds['gpu_memory_critical']:
            issues.append(f"GPU内存使用率过高: {gpu_memory_percent:.1f}%")
            recommendations.append("建议减少GPU处理负载")
        elif gpu_memory_percent >= self.thresholds['gpu_memory_high']:
            issues.append(f"GPU内存使用率较高: {gpu_memory_percent:.1f}%")
            recommendations.append("建议监控GPU内存使用")
            
        # 确定整体状态
        if any("过高" in issue for issue in issues):
            status = 'critical'
            message = '系统资源使用率过高，可能影响性能'
        elif any("较高" in issue for issue in issues):
            status = 'warning'
            message = '系统资源使用率较高，建议关注'
        else:
            status = 'good'
            message = '系统资源使用正常'
            
        return {
            'status': status,
            'message': message,
            'issues': issues,
            'recommendations': recommendations,
            'metrics': {
                'cpu_percent': current.cpu_percent,
                'memory_percent': current.memory_percent,
                'gpu_memory_percent': gpu_memory_percent,
                'disk_io_read_mbps': current.disk_io_read,
                'disk_io_write_mbps': current.disk_io_write
            }
        }
        
    def get_processing_recommendations(self) -> Dict[str, Any]:
        """获取视频处理的性能建议"""
        status = self.get_performance_status()
        
        recommendations = {
            'should_process': True,
            'max_concurrent_tasks': 1,
            'frame_skip_interval': 0,
            'sleep_interval': 0.005,
            'reason': '系统资源充足'
        }
        
        if status['status'] == 'critical':
            recommendations.update({
                'should_process': False,
                'reason': '系统资源不足，建议暂停处理'
            })
        elif status['status'] == 'warning':
            recommendations.update({
                'max_concurrent_tasks': 1,
                'frame_skip_interval': 0,
                'sleep_interval': 0.02,  # 增加让步时间
                'reason': '系统资源紧张，降低处理强度'
            })
            
        return recommendations

# 全局性能监控器实例
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

def start_performance_monitoring():
    """启动性能监控"""
    monitor = get_performance_monitor()
    monitor.start_monitoring()

def stop_performance_monitoring():
    """停止性能监控"""
    monitor = get_performance_monitor()
    monitor.stop_monitoring() 