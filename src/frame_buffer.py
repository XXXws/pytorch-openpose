#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧缓冲队列管理模块
实现高效的帧数据缓冲和流转机制
"""

import threading
import time
import queue
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import deque
import logging

from .memory_pool import get_memory_manager, ManagedArray
from .pipeline import FrameData

logger = logging.getLogger(__name__)

@dataclass
class BufferConfig:
    """缓冲区配置"""
    max_size: int = 10              # 最大缓冲帧数
    drop_policy: str = "oldest"     # 丢帧策略: "oldest", "newest", "adaptive"
    enable_compression: bool = False # 是否启用压缩
    compression_quality: int = 85    # 压缩质量 (1-100)
    auto_resize: bool = True        # 是否自动调整缓冲区大小

class FrameBuffer:
    """帧缓冲区"""
    
    def __init__(self, config: BufferConfig):
        self.config = config
        self.buffer: deque = deque(maxsize=config.max_size)
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_frames_in': 0,
            'total_frames_out': 0,
            'frames_dropped': 0,
            'buffer_full_count': 0,
            'avg_buffer_size': 0.0,
            'peak_buffer_size': 0,
            'compression_ratio': 1.0
        }
        
        # 性能监控
        self.size_history = deque(maxsize=100)
        self.memory_manager = get_memory_manager()
        
    def put(self, frame_data: FrameData, timeout: Optional[float] = None) -> bool:
        """添加帧到缓冲区"""
        with self.lock:
            try:
                # 检查缓冲区是否已满
                if len(self.buffer) >= self.config.max_size:
                    self.stats['buffer_full_count'] += 1
                    
                    # 根据丢帧策略处理
                    if self.config.drop_policy == "oldest":
                        # 丢弃最旧的帧
                        if self.buffer:
                            dropped_frame = self.buffer.popleft()
                            self._cleanup_frame(dropped_frame)
                            self.stats['frames_dropped'] += 1
                    elif self.config.drop_policy == "newest":
                        # 丢弃新帧
                        self.stats['frames_dropped'] += 1
                        return False
                    elif self.config.drop_policy == "adaptive":
                        # 自适应丢帧：根据帧的重要性决定
                        if not self._adaptive_drop_frame(frame_data):
                            self.stats['frames_dropped'] += 1
                            return False
                
                # 可选的帧压缩
                if self.config.enable_compression:
                    frame_data = self._compress_frame(frame_data)
                
                # 添加帧到缓冲区
                self.buffer.append(frame_data)
                self.stats['total_frames_in'] += 1
                
                # 更新统计信息
                current_size = len(self.buffer)
                self.size_history.append(current_size)
                if current_size > self.stats['peak_buffer_size']:
                    self.stats['peak_buffer_size'] = current_size
                
                return True
                
            except Exception as e:
                logger.error(f"Error adding frame to buffer: {e}")
                return False
    
    def get(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """从缓冲区获取帧"""
        with self.lock:
            try:
                if not self.buffer:
                    return None
                
                frame_data = self.buffer.popleft()
                self.stats['total_frames_out'] += 1
                
                # 解压缩帧（如果需要）
                if self.config.enable_compression:
                    frame_data = self._decompress_frame(frame_data)
                
                return frame_data
                
            except Exception as e:
                logger.error(f"Error getting frame from buffer: {e}")
                return None
    
    def peek(self) -> Optional[FrameData]:
        """查看缓冲区中的下一帧（不移除）"""
        with self.lock:
            if self.buffer:
                return self.buffer[0]
            return None
    
    def size(self) -> int:
        """获取当前缓冲区大小"""
        with self.lock:
            return len(self.buffer)
    
    def is_empty(self) -> bool:
        """检查缓冲区是否为空"""
        with self.lock:
            return len(self.buffer) == 0
    
    def is_full(self) -> bool:
        """检查缓冲区是否已满"""
        with self.lock:
            return len(self.buffer) >= self.config.max_size
    
    def clear(self):
        """清空缓冲区"""
        with self.lock:
            while self.buffer:
                frame_data = self.buffer.popleft()
                self._cleanup_frame(frame_data)
            logger.info("Frame buffer cleared")
    
    def _adaptive_drop_frame(self, new_frame: FrameData) -> bool:
        """自适应丢帧策略"""
        if not self.buffer:
            return True
        
        # 简单的自适应策略：比较帧的时间戳
        # 如果新帧比缓冲区中最新的帧更新，则丢弃最旧的帧
        newest_frame = self.buffer[-1]
        if new_frame.timestamp > newest_frame.timestamp:
            oldest_frame = self.buffer.popleft()
            self._cleanup_frame(oldest_frame)
            return True
        
        return False
    
    def _compress_frame(self, frame_data: FrameData) -> FrameData:
        """压缩帧数据"""
        try:
            import cv2
            
            # 压缩图像
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.config.compression_quality]
            _, compressed_data = cv2.imencode('.jpg', frame_data.image, encode_param)
            
            # 计算压缩比
            original_size = frame_data.image.nbytes
            compressed_size = len(compressed_data)
            compression_ratio = compressed_size / original_size
            
            # 更新统计信息
            self.stats['compression_ratio'] = (
                self.stats['compression_ratio'] * 0.9 + compression_ratio * 0.1
            )
            
            # 创建新的帧数据对象
            compressed_frame = FrameData(
                frame_id=frame_data.frame_id,
                timestamp=frame_data.timestamp,
                image=compressed_data,  # 存储压缩数据
                metadata={**frame_data.metadata, 'compressed': True}
            )
            
            return compressed_frame
            
        except Exception as e:
            logger.warning(f"Frame compression failed: {e}")
            return frame_data
    
    def _decompress_frame(self, frame_data: FrameData) -> FrameData:
        """解压缩帧数据"""
        try:
            if frame_data.metadata.get('compressed', False):
                import cv2
                
                # 解压缩图像
                image = cv2.imdecode(frame_data.image, cv2.IMREAD_COLOR)
                
                # 创建新的帧数据对象
                decompressed_frame = FrameData(
                    frame_id=frame_data.frame_id,
                    timestamp=frame_data.timestamp,
                    image=image,
                    metadata={k: v for k, v in frame_data.metadata.items() if k != 'compressed'}
                )
                
                return decompressed_frame
            
            return frame_data
            
        except Exception as e:
            logger.error(f"Frame decompression failed: {e}")
            return frame_data
    
    def _cleanup_frame(self, frame_data: FrameData):
        """清理帧数据，释放资源"""
        try:
            # 如果图像数据来自内存池，归还给内存池
            if hasattr(frame_data, '_managed_memory') and frame_data._managed_memory:
                if isinstance(frame_data.image, np.ndarray):
                    self.memory_manager.return_cpu_array(frame_data.image)
            
            # 清理其他资源
            frame_data.image = None
            frame_data.body_candidate = None
            frame_data.body_subset = None
            frame_data.hand_peaks = None
            frame_data.rendered_image = None
            
        except Exception as e:
            logger.warning(f"Error cleaning up frame: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓冲区统计信息"""
        with self.lock:
            # 计算平均缓冲区大小
            if self.size_history:
                avg_size = sum(self.size_history) / len(self.size_history)
            else:
                avg_size = 0.0
            
            return {
                'current_size': len(self.buffer),
                'max_size': self.config.max_size,
                'total_frames_in': self.stats['total_frames_in'],
                'total_frames_out': self.stats['total_frames_out'],
                'frames_dropped': self.stats['frames_dropped'],
                'buffer_full_count': self.stats['buffer_full_count'],
                'avg_buffer_size': avg_size,
                'peak_buffer_size': self.stats['peak_buffer_size'],
                'drop_rate': (self.stats['frames_dropped'] / 
                             max(1, self.stats['total_frames_in'])),
                'compression_ratio': self.stats['compression_ratio'],
                'config': {
                    'max_size': self.config.max_size,
                    'drop_policy': self.config.drop_policy,
                    'enable_compression': self.config.enable_compression,
                    'compression_quality': self.config.compression_quality
                }
            }

class MultiStageFrameBuffer:
    """多阶段帧缓冲管理器"""
    
    def __init__(self, stage_configs: Dict[str, BufferConfig]):
        self.buffers: Dict[str, FrameBuffer] = {}
        self.lock = threading.RLock()
        
        # 创建各阶段的缓冲区
        for stage_name, config in stage_configs.items():
            self.buffers[stage_name] = FrameBuffer(config)
        
        logger.info(f"Multi-stage frame buffer initialized with {len(self.buffers)} stages")
    
    def get_buffer(self, stage_name: str) -> Optional[FrameBuffer]:
        """获取指定阶段的缓冲区"""
        return self.buffers.get(stage_name)
    
    def put_frame(self, stage_name: str, frame_data: FrameData, timeout: Optional[float] = None) -> bool:
        """向指定阶段添加帧"""
        buffer = self.get_buffer(stage_name)
        if buffer:
            return buffer.put(frame_data, timeout)
        return False
    
    def get_frame(self, stage_name: str, timeout: Optional[float] = None) -> Optional[FrameData]:
        """从指定阶段获取帧"""
        buffer = self.get_buffer(stage_name)
        if buffer:
            return buffer.get(timeout)
        return None
    
    def clear_all(self):
        """清空所有缓冲区"""
        with self.lock:
            for buffer in self.buffers.values():
                buffer.clear()
        logger.info("All frame buffers cleared")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有缓冲区的统计信息"""
        with self.lock:
            stats = {}
            total_frames_in = 0
            total_frames_out = 0
            total_frames_dropped = 0
            
            for stage_name, buffer in self.buffers.items():
                buffer_stats = buffer.get_stats()
                stats[stage_name] = buffer_stats
                
                total_frames_in += buffer_stats['total_frames_in']
                total_frames_out += buffer_stats['total_frames_out']
                total_frames_dropped += buffer_stats['frames_dropped']
            
            # 总体统计
            stats['summary'] = {
                'total_stages': len(self.buffers),
                'total_frames_in': total_frames_in,
                'total_frames_out': total_frames_out,
                'total_frames_dropped': total_frames_dropped,
                'overall_drop_rate': total_frames_dropped / max(1, total_frames_in)
            }
            
            return stats

class AdaptiveFrameBuffer:
    """自适应帧缓冲区"""
    
    def __init__(self, initial_config: BufferConfig, 
                 performance_monitor: Optional[Callable[[], Dict[str, Any]]] = None):
        self.base_config = initial_config
        self.current_config = BufferConfig(**initial_config.__dict__)
        self.buffer = FrameBuffer(self.current_config)
        self.performance_monitor = performance_monitor
        
        # 自适应参数
        self.adaptation_interval = 5.0  # 秒
        self.last_adaptation_time = time.time()
        self.performance_history = deque(maxsize=10)
        
        # 自适应线程
        self.adaptation_thread = None
        self.adaptation_running = False
        self.start_adaptation()
    
    def start_adaptation(self):
        """启动自适应调整"""
        if self.adaptation_running:
            return
        
        self.adaptation_running = True
        self.adaptation_thread = threading.Thread(target=self._adaptation_loop, daemon=True)
        self.adaptation_thread.start()
        logger.info("Adaptive frame buffer started")
    
    def stop_adaptation(self):
        """停止自适应调整"""
        self.adaptation_running = False
        if self.adaptation_thread:
            self.adaptation_thread.join(timeout=2.0)
        logger.info("Adaptive frame buffer stopped")
    
    def _adaptation_loop(self):
        """自适应调整循环"""
        while self.adaptation_running:
            try:
                time.sleep(self.adaptation_interval)
                
                if self.performance_monitor:
                    performance_data = self.performance_monitor()
                    self.performance_history.append(performance_data)
                    
                    # 执行自适应调整
                    self._adapt_buffer_config()
                
            except Exception as e:
                logger.error(f"Adaptive buffer error: {e}")
    
    def _adapt_buffer_config(self):
        """根据性能数据调整缓冲区配置"""
        if len(self.performance_history) < 3:
            return
        
        # 分析性能趋势
        recent_performance = list(self.performance_history)[-3:]
        
        # 计算平均丢帧率
        avg_drop_rate = sum(p.get('drop_rate', 0) for p in recent_performance) / len(recent_performance)
        
        # 计算平均处理延迟
        avg_latency = sum(p.get('avg_latency', 0) for p in recent_performance) / len(recent_performance)
        
        # 自适应调整策略
        new_config = BufferConfig(**self.current_config.__dict__)
        
        # 如果丢帧率过高，增加缓冲区大小
        if avg_drop_rate > 0.1 and self.current_config.max_size < 20:
            new_config.max_size = min(20, self.current_config.max_size + 2)
            logger.info(f"Increased buffer size to {new_config.max_size} due to high drop rate")
        
        # 如果延迟过高，减少缓冲区大小
        elif avg_latency > 0.5 and self.current_config.max_size > 5:
            new_config.max_size = max(5, self.current_config.max_size - 1)
            logger.info(f"Decreased buffer size to {new_config.max_size} due to high latency")
        
        # 如果性能良好，启用压缩以节省内存
        if avg_drop_rate < 0.05 and avg_latency < 0.2:
            if not self.current_config.enable_compression:
                new_config.enable_compression = True
                logger.info("Enabled compression due to good performance")
        
        # 应用新配置
        if new_config.__dict__ != self.current_config.__dict__:
            self._apply_new_config(new_config)
    
    def _apply_new_config(self, new_config: BufferConfig):
        """应用新的缓冲区配置"""
        old_buffer = self.buffer
        self.current_config = new_config
        self.buffer = FrameBuffer(new_config)
        
        # 迁移现有帧到新缓冲区
        while not old_buffer.is_empty():
            frame = old_buffer.get()
            if frame and not self.buffer.put(frame):
                break
        
        old_buffer.clear()
    
    def put(self, frame_data: FrameData, timeout: Optional[float] = None) -> bool:
        """添加帧到缓冲区"""
        return self.buffer.put(frame_data, timeout)
    
    def get(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """从缓冲区获取帧"""
        return self.buffer.get(timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.buffer.get_stats()
        stats['adaptive'] = {
            'adaptation_running': self.adaptation_running,
            'adaptation_interval': self.adaptation_interval,
            'performance_history_size': len(self.performance_history),
            'current_config': self.current_config.__dict__,
            'base_config': self.base_config.__dict__
        }
        return stats

# 工厂函数
def create_default_frame_buffers() -> MultiStageFrameBuffer:
    """创建默认的多阶段帧缓冲区"""
    stage_configs = {
        'capture': BufferConfig(max_size=5, drop_policy="oldest"),
        'preprocess': BufferConfig(max_size=8, drop_policy="adaptive"),
        'body_inference': BufferConfig(max_size=10, drop_policy="adaptive"),
        'hand_inference': BufferConfig(max_size=8, drop_policy="adaptive"),
        'postprocess': BufferConfig(max_size=5, drop_policy="newest"),
        'render': BufferConfig(max_size=3, drop_policy="newest")
    }
    
    return MultiStageFrameBuffer(stage_configs) 