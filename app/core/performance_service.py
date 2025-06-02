#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控服务模块
实现第203-210行计划中的性能测试和优化监控功能
"""

import time
import psutil
import torch
import GPUtil
import threading
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np

# 导入检测服务
from .detection_service import get_detection_service

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None
        self.performance_data = {
            "system": {
                "cpu_usage": [],
                "memory_usage": [],
                "gpu_usage": [],
                "gpu_memory": [],
                "timestamps": []
            },
            "detection": {
                "api_response_times": [],
                "concurrent_requests": [],
                "websocket_fps": [],
                "processing_times": []
            },
            "baseline": None
        }
        
        # 检测可用的GPU
        self.gpu_available = torch.cuda.is_available()
        if self.gpu_available:
            self.gpus = GPUtil.getGPUs()
        else:
            self.gpus = []
    
    def start_monitoring(self, interval: float = 1.0):
        """开始性能监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        print(f"性能监控已启动，采样间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        print("性能监控已停止")
    
    def _monitor_loop(self, interval: float):
        """监控循环"""
        while self.monitoring:
            try:
                current_time = time.time()
                
                # 系统性能数据
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                
                # GPU性能数据
                gpu_usage = 0
                gpu_memory = 0
                if self.gpu_available and self.gpus:
                    gpu = self.gpus[0]  # 使用第一个GPU
                    gpu_usage = gpu.load * 100
                    gpu_memory = gpu.memoryUtil * 100
                
                # 存储数据
                self.performance_data["system"]["cpu_usage"].append(cpu_percent)
                self.performance_data["system"]["memory_usage"].append(memory_percent)
                self.performance_data["system"]["gpu_usage"].append(gpu_usage)
                self.performance_data["system"]["gpu_memory"].append(gpu_memory)
                self.performance_data["system"]["timestamps"].append(current_time)
                
                # 保持最近1000个数据点
                for key in self.performance_data["system"]:
                    if len(self.performance_data["system"][key]) > 1000:
                        self.performance_data["system"][key] = self.performance_data["system"][key][-1000:]
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"性能监控错误: {e}")
                time.sleep(interval)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前性能统计"""
        stats = {
            "timestamp": time.time(),
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory": dict(psutil.virtual_memory()._asdict()),
                "disk": dict(psutil.disk_usage('/')._asdict()) if os.name != 'nt' else dict(psutil.disk_usage('C:')._asdict())
            },
            "gpu": {
                "available": self.gpu_available,
                "count": len(self.gpus) if self.gpus else 0
            }
        }
        
        # GPU详细信息
        if self.gpu_available and self.gpus:
            gpu_info = []
            for gpu in self.gpus:
                gpu_info.append({
                    "id": gpu.id,
                    "name": gpu.name,
                    "load": gpu.load,
                    "memory_used": gpu.memoryUsed,
                    "memory_total": gpu.memoryTotal,
                    "memory_util": gpu.memoryUtil,
                    "temperature": gpu.temperature
                })
            stats["gpu"]["devices"] = gpu_info
        
        return stats
    
    def record_api_response(self, response_time: float, concurrent_count: int = 1):
        """记录API响应时间"""
        self.performance_data["detection"]["api_response_times"].append({
            "response_time": response_time,
            "timestamp": time.time(),
            "concurrent_count": concurrent_count
        })
        
        # 保持最近500个记录
        if len(self.performance_data["detection"]["api_response_times"]) > 500:
            self.performance_data["detection"]["api_response_times"] = self.performance_data["detection"]["api_response_times"][-500:]
    
    def record_websocket_fps(self, fps: float, client_id: str):
        """记录WebSocket FPS"""
        self.performance_data["detection"]["websocket_fps"].append({
            "fps": fps,
            "client_id": client_id,
            "timestamp": time.time()
        })
        
        # 保持最近200个记录
        if len(self.performance_data["detection"]["websocket_fps"]) > 200:
            self.performance_data["detection"]["websocket_fps"] = self.performance_data["detection"]["websocket_fps"][-200:]
    
    def run_baseline_test(self) -> Dict[str, Any]:
        """
        运行基准性能测试
        基于demo.py脚本建立性能基准
        """
        print("开始基准性能测试...")
        
        detection_service = get_detection_service()
        baseline_results = {
            "test_time": datetime.now().isoformat(),
            "device": str(detection_service.device),
            "single_image": {},
            "batch_processing": {},
            "system_info": self.get_current_stats()
        }
        
        # 创建测试图像
        test_images = [
            np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
            np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8),
            np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        ]
        
        # 单图像性能测试
        for i, test_image in enumerate(test_images):
            size_name = ["480p", "720p", "1080p"][i]
            times = []
            
            # 预热
            detection_service.detect_pose(test_image, draw_result=False)
            
            # 多次测试
            for _ in range(10):
                start_time = time.time()
                result = detection_service.detect_pose(
                    image=test_image,
                    include_body=True,
                    include_hands=True,
                    draw_result=False
                )
                end_time = time.time()
                
                if result["success"]:
                    times.append(end_time - start_time)
            
            if times:
                baseline_results["single_image"][size_name] = {
                    "mean_time": np.mean(times),
                    "std_time": np.std(times),
                    "min_time": np.min(times),
                    "max_time": np.max(times),
                    "fps": 1.0 / np.mean(times)
                }
        
        # 批处理性能测试
        batch_sizes = [1, 3, 5]
        for batch_size in batch_sizes:
            batch_times = []
            
            for _ in range(5):
                start_time = time.time()
                
                for _ in range(batch_size):
                    result = detection_service.detect_pose(
                        image=test_images[0],  # 使用480p图像
                        include_body=True,
                        include_hands=True,
                        draw_result=False
                    )
                
                end_time = time.time()
                batch_times.append(end_time - start_time)
            
            if batch_times:
                baseline_results["batch_processing"][f"batch_{batch_size}"] = {
                    "mean_time": np.mean(batch_times),
                    "throughput": batch_size / np.mean(batch_times)
                }
        
        self.performance_data["baseline"] = baseline_results
        print("基准性能测试完成")
        
        return baseline_results
    
    def run_concurrent_test(self, num_clients: int = 5, duration: int = 30) -> Dict[str, Any]:
        """
        运行并发测试
        测试多客户端同时调用API的性能表现
        """
        print(f"开始并发测试: {num_clients}个客户端, 持续{duration}秒")
        
        import concurrent.futures
        import requests
        
        results = {
            "test_config": {
                "num_clients": num_clients,
                "duration": duration,
                "start_time": datetime.now().isoformat()
            },
            "client_results": [],
            "summary": {}
        }
        
        def client_worker(client_id: int):
            """单个客户端工作函数"""
            client_stats = {
                "client_id": client_id,
                "requests_completed": 0,
                "total_response_time": 0,
                "errors": 0,
                "response_times": []
            }
            
            start_time = time.time()
            
            while time.time() - start_time < duration:
                try:
                    request_start = time.time()
                    
                    # 发送API请求（这里应该调用实际的API）
                    # 这是一个示例，实际实现时需要调用检测API
                    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                    detection_service = get_detection_service()
                    result = detection_service.detect_pose(test_image, draw_result=False)
                    
                    request_end = time.time()
                    response_time = request_end - request_start
                    
                    client_stats["requests_completed"] += 1
                    client_stats["total_response_time"] += response_time
                    client_stats["response_times"].append(response_time)
                    
                    # 记录性能数据
                    self.record_api_response(response_time, num_clients)
                    
                except Exception as e:
                    client_stats["errors"] += 1
                    print(f"客户端 {client_id} 请求错误: {e}")
                
                time.sleep(0.1)  # 避免过于频繁的请求
            
            return client_stats
        
        # 执行并发测试
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = [executor.submit(client_worker, i) for i in range(num_clients)]
            client_results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        results["client_results"] = client_results
        
        # 计算总结统计
        total_requests = sum(client["requests_completed"] for client in client_results)
        total_errors = sum(client["errors"] for client in client_results)
        all_response_times = []
        for client in client_results:
            all_response_times.extend(client["response_times"])
        
        if all_response_times:
            results["summary"] = {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": total_errors / max(total_requests + total_errors, 1),
                "throughput": total_requests / duration,
                "mean_response_time": np.mean(all_response_times),
                "p95_response_time": np.percentile(all_response_times, 95),
                "p99_response_time": np.percentile(all_response_times, 99)
            }
        
        print(f"并发测试完成: {total_requests}个请求, {total_errors}个错误")
        
        return results
    
    def check_memory_leaks(self, duration: int = 1800) -> Dict[str, Any]:
        """
        内存泄露检测
        长时间运行测试（30分钟），监控内存使用增长趋势
        """
        print(f"开始内存泄露检测，持续{duration}秒...")
        
        detection_service = get_detection_service()
        memory_samples = []
        start_time = time.time()
        
        # 记录初始内存状态
        initial_memory = psutil.virtual_memory()
        if self.gpu_available:
            initial_gpu_memory = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        while time.time() - start_time < duration:
            try:
                # 执行检测任务
                result = detection_service.detect_pose(test_image, draw_result=True)
                
                # 记录内存使用
                current_memory = psutil.virtual_memory()
                sample = {
                    "timestamp": time.time() - start_time,
                    "memory_percent": current_memory.percent,
                    "memory_used_mb": current_memory.used / 1024 / 1024
                }
                
                if self.gpu_available:
                    sample["gpu_memory_mb"] = torch.cuda.memory_allocated() / 1024 / 1024
                
                memory_samples.append(sample)
                
                time.sleep(5)  # 每5秒检测一次
                
            except Exception as e:
                print(f"内存检测错误: {e}")
                break
        
        # 分析结果
        if len(memory_samples) >= 2:
            first_sample = memory_samples[0]
            last_sample = memory_samples[-1]
            
            memory_growth = last_sample["memory_used_mb"] - first_sample["memory_used_mb"]
            growth_rate = memory_growth / (duration / 3600)  # MB per hour
            
            analysis = {
                "test_duration": duration,
                "samples_count": len(memory_samples),
                "initial_memory_mb": first_sample["memory_used_mb"],
                "final_memory_mb": last_sample["memory_used_mb"],
                "memory_growth_mb": memory_growth,
                "growth_rate_mb_per_hour": growth_rate,
                "samples": memory_samples,
                "has_leak": growth_rate > 100  # 如果每小时增长超过100MB认为有泄露
            }
            
            if self.gpu_available and "gpu_memory_mb" in first_sample:
                gpu_growth = last_sample["gpu_memory_mb"] - first_sample["gpu_memory_mb"]
                analysis["gpu_memory_growth_mb"] = gpu_growth
        else:
            analysis = {"error": "测试时间不足，无法分析"}
        
        print(f"内存泄露检测完成，增长率: {analysis.get('growth_rate_mb_per_hour', 0):.2f} MB/小时")
        
        return analysis
    
    def export_performance_report(self, filepath: str = None) -> str:
        """导出性能报告"""
        if filepath is None:
            filepath = f"performance_report_{int(time.time())}.json"
        
        report = {
            "export_time": datetime.now().isoformat(),
            "performance_data": self.performance_data,
            "current_stats": self.get_current_stats()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"性能报告已导出: {filepath}")
        return filepath

# 全局性能监控器实例
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor 