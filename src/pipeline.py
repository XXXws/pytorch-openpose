#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步流水线架构模块
实现多阶段并行处理，提升视频处理和实时检测性能
"""

import asyncio
import threading
import queue
import time
import numpy as np
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PipelineStage(Enum):
    """流水线阶段枚举"""
    CAPTURE = "capture"           # 帧捕获
    PREPROCESS = "preprocess"     # 预处理
    BODY_INFERENCE = "body_inference"  # 身体推理
    HAND_INFERENCE = "hand_inference"  # 手部推理
    POSTPROCESS = "postprocess"   # 后处理
    RENDER = "render"            # 渲染输出

@dataclass
class FrameData:
    """帧数据结构"""
    frame_id: int
    timestamp: float
    image: np.ndarray
    metadata: Dict[str, Any]
    
    # 处理结果
    body_candidate: Optional[np.ndarray] = None
    body_subset: Optional[np.ndarray] = None
    hand_peaks: Optional[List[np.ndarray]] = None
    rendered_image: Optional[np.ndarray] = None
    
    # 性能指标
    stage_times: Dict[str, float] = None
    
    def __post_init__(self):
        if self.stage_times is None:
            self.stage_times = {}

class PipelineWorker:
    """流水线工作器基类"""
    
    def __init__(self, stage: PipelineStage, input_queue: queue.Queue, 
                 output_queue: queue.Queue, max_queue_size: int = 10):
        self.stage = stage
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.max_queue_size = max_queue_size
        self.running = False
        self.thread = None
        self.stats = {
            'processed_frames': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'queue_full_drops': 0
        }
    
    def start(self):
        """启动工作器"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        logger.info(f"{self.stage.value} worker started")
    
    def stop(self):
        """停止工作器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info(f"{self.stage.value} worker stopped")
    
    def _worker_loop(self):
        """工作器主循环"""
        while self.running:
            try:
                # 从输入队列获取数据
                frame_data = self.input_queue.get(timeout=1.0)
                
                # 记录处理开始时间
                start_time = time.time()
                
                # 执行处理
                processed_data = self.process(frame_data)
                
                # 记录处理时间
                process_time = time.time() - start_time
                processed_data.stage_times[self.stage.value] = process_time
                
                # 更新统计信息
                self.stats['processed_frames'] += 1
                self.stats['total_time'] += process_time
                self.stats['avg_time'] = self.stats['total_time'] / self.stats['processed_frames']
                
                # 输出到下一阶段
                try:
                    self.output_queue.put(processed_data, timeout=0.1)
                except queue.Full:
                    # 队列满时丢弃帧
                    self.stats['queue_full_drops'] += 1
                    logger.warning(f"{self.stage.value}: Output queue full, dropping frame {frame_data.frame_id}")
                
                self.input_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"{self.stage.value} worker error: {e}")
                continue
    
    def process(self, frame_data: FrameData) -> FrameData:
        """处理函数，子类需要重写"""
        raise NotImplementedError("Subclasses must implement process method")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

class AsyncPipeline:
    """异步流水线管理器"""
    
    def __init__(self, max_queue_size: int = 10):
        self.max_queue_size = max_queue_size
        self.workers: Dict[PipelineStage, PipelineWorker] = {}
        self.queues: Dict[PipelineStage, queue.Queue] = {}
        self.running = False
        
        # 创建队列
        for stage in PipelineStage:
            self.queues[stage] = queue.Queue(maxsize=max_queue_size)
        
        # 性能监控
        self.performance_monitor = PerformanceMonitor()
    
    def add_worker(self, worker: PipelineWorker):
        """添加工作器"""
        self.workers[worker.stage] = worker
        logger.info(f"Added worker for stage: {worker.stage.value}")
    
    def start(self):
        """启动流水线"""
        if self.running:
            return
        
        self.running = True
        
        # 启动所有工作器
        for worker in self.workers.values():
            worker.start()
        
        # 启动性能监控
        self.performance_monitor.start()
        
        logger.info("Pipeline started")
    
    def stop(self):
        """停止流水线"""
        if not self.running:
            return
        
        self.running = False
        
        # 停止所有工作器
        for worker in self.workers.values():
            worker.stop()
        
        # 停止性能监控
        self.performance_monitor.stop()
        
        logger.info("Pipeline stopped")
    
    def submit_frame(self, frame_data: FrameData) -> bool:
        """提交帧到流水线"""
        try:
            first_stage = PipelineStage.CAPTURE
            if first_stage in self.queues:
                self.queues[first_stage].put(frame_data, timeout=0.1)
                return True
        except queue.Full:
            logger.warning(f"Pipeline input queue full, dropping frame {frame_data.frame_id}")
            return False
        return False
    
    def get_result(self, timeout: float = 1.0) -> Optional[FrameData]:
        """获取处理结果"""
        try:
            last_stage = PipelineStage.RENDER
            if last_stage in self.queues:
                return self.queues[last_stage].get(timeout=timeout)
        except queue.Empty:
            return None
        return None
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """获取流水线统计信息"""
        stats = {
            'running': self.running,
            'workers': {},
            'queues': {},
            'performance': self.performance_monitor.get_stats()
        }
        
        # 工作器统计
        for stage, worker in self.workers.items():
            stats['workers'][stage.value] = worker.get_stats()
        
        # 队列统计
        for stage, q in self.queues.items():
            stats['queues'][stage.value] = {
                'size': q.qsize(),
                'max_size': q.maxsize
            }
        
        return stats

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.stats = {
            'total_frames': 0,
            'fps': 0.0,
            'avg_latency': 0.0,
            'start_time': 0.0
        }
        self.frame_times = []
        self.max_history = 100
    
    def start(self):
        """启动监控"""
        if self.running:
            return
        
        self.running = True
        self.stats['start_time'] = time.time()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
    
    def record_frame(self, frame_data: FrameData):
        """记录帧处理信息"""
        current_time = time.time()
        latency = current_time - frame_data.timestamp
        
        self.frame_times.append(latency)
        if len(self.frame_times) > self.max_history:
            self.frame_times.pop(0)
        
        self.stats['total_frames'] += 1
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 计算FPS
                elapsed_time = time.time() - self.stats['start_time']
                if elapsed_time > 0:
                    self.stats['fps'] = self.stats['total_frames'] / elapsed_time
                
                # 计算平均延迟
                if self.frame_times:
                    self.stats['avg_latency'] = sum(self.frame_times) / len(self.frame_times)
                
                time.sleep(1.0)  # 每秒更新一次
                
            except Exception as e:
                logger.error(f"Performance monitor error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()

# 工厂函数
def create_optimized_pipeline(max_queue_size: int = 10) -> AsyncPipeline:
    """创建优化的流水线实例"""
    pipeline = AsyncPipeline(max_queue_size)
    
    # 这里可以添加默认的工作器
    # 具体的工作器实现将在后续步骤中添加
    
    return pipeline 
