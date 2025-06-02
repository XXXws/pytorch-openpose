#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存池管理模块
优化GPU和CPU内存分配，减少频繁分配/释放开销
"""

import torch
import numpy as np
import threading
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class MemoryBlock:
    """内存块信息"""
    size: Tuple[int, ...]  # 内存块尺寸
    dtype: Any             # 数据类型
    device: str            # 设备类型
    tensor: Optional[torch.Tensor] = None
    array: Optional[np.ndarray] = None
    in_use: bool = False
    created_time: float = 0.0
    last_used_time: float = 0.0

class GPUMemoryPool:
    """GPU内存池管理器"""
    
    def __init__(self, device: str = "cuda", max_pool_size_mb: int = 1024):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.max_pool_size = max_pool_size_mb * 1024 * 1024  # 转换为字节
        self.current_pool_size = 0
        
        # 内存池：按尺寸和数据类型分组
        self.pools: Dict[Tuple[Tuple[int, ...], Any], List[MemoryBlock]] = defaultdict(list)
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_allocations': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'memory_saved_mb': 0.0,
            'peak_usage_mb': 0.0
        }
        
        logger.info(f"GPU Memory Pool initialized on {self.device}, max size: {max_pool_size_mb}MB")
    
    def get_tensor(self, shape: Tuple[int, ...], dtype: torch.dtype = torch.float32) -> torch.Tensor:
        """从内存池获取张量"""
        with self.lock:
            key = (shape, dtype)
            pool = self.pools[key]
            
            # 查找可用的内存块
            for block in pool:
                if not block.in_use:
                    block.in_use = True
                    block.last_used_time = time.time()
                    self.stats['pool_hits'] += 1
                    return block.tensor
            
            # 没有可用的内存块，创建新的
            tensor = self._create_tensor(shape, dtype)
            block = MemoryBlock(
                size=shape,
                dtype=dtype,
                device=str(self.device),
                tensor=tensor,
                in_use=True,
                created_time=time.time(),
                last_used_time=time.time()
            )
            
            pool.append(block)
            self.stats['pool_misses'] += 1
            self.stats['total_allocations'] += 1
            
            return tensor
    
    def return_tensor(self, tensor: torch.Tensor):
        """归还张量到内存池"""
        with self.lock:
            # 查找对应的内存块
            for pool in self.pools.values():
                for block in pool:
                    if block.tensor is tensor:
                        block.in_use = False
                        block.last_used_time = time.time()
                        return
            
            logger.warning("Attempted to return tensor not from pool")
    
    def _create_tensor(self, shape: Tuple[int, ...], dtype: torch.dtype) -> torch.Tensor:
        """创建新的张量"""
        try:
            tensor = torch.empty(shape, dtype=dtype, device=self.device)
            
            # 更新内存使用统计
            tensor_size = tensor.numel() * tensor.element_size()
            self.current_pool_size += tensor_size
            
            current_mb = self.current_pool_size / 1024 / 1024
            if current_mb > self.stats['peak_usage_mb']:
                self.stats['peak_usage_mb'] = current_mb
            
            return tensor
            
        except torch.cuda.OutOfMemoryError:
            # GPU内存不足，尝试清理
            self._cleanup_unused_blocks()
            torch.cuda.empty_cache()
            
            # 再次尝试分配
            try:
                return torch.empty(shape, dtype=dtype, device=self.device)
            except torch.cuda.OutOfMemoryError:
                logger.error(f"Failed to allocate GPU memory for shape {shape}")
                raise
    
    def _cleanup_unused_blocks(self, max_age_seconds: float = 300.0):
        """清理长时间未使用的内存块"""
        with self.lock:
            current_time = time.time()
            cleaned_count = 0
            
            for key, pool in list(self.pools.items()):
                # 过滤掉长时间未使用的块
                new_pool = []
                for block in pool:
                    if (not block.in_use and 
                        current_time - block.last_used_time > max_age_seconds):
                        # 释放内存
                        if block.tensor is not None:
                            tensor_size = block.tensor.numel() * block.tensor.element_size()
                            self.current_pool_size -= tensor_size
                            del block.tensor
                        cleaned_count += 1
                    else:
                        new_pool.append(block)
                
                if new_pool:
                    self.pools[key] = new_pool
                else:
                    del self.pools[key]
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} unused memory blocks")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取内存池统计信息"""
        with self.lock:
            total_blocks = sum(len(pool) for pool in self.pools.values())
            in_use_blocks = sum(1 for pool in self.pools.values() 
                              for block in pool if block.in_use)
            
            hit_rate = (self.stats['pool_hits'] / 
                       max(1, self.stats['pool_hits'] + self.stats['pool_misses']))
            
            return {
                'device': str(self.device),
                'total_blocks': total_blocks,
                'in_use_blocks': in_use_blocks,
                'current_size_mb': self.current_pool_size / 1024 / 1024,
                'peak_usage_mb': self.stats['peak_usage_mb'],
                'hit_rate': hit_rate,
                'total_allocations': self.stats['total_allocations'],
                'pool_hits': self.stats['pool_hits'],
                'pool_misses': self.stats['pool_misses']
            }

class CPUMemoryPool:
    """CPU内存池管理器"""
    
    def __init__(self, max_pool_size_mb: int = 512):
        self.max_pool_size = max_pool_size_mb * 1024 * 1024
        self.current_pool_size = 0
        
        # 内存池：按尺寸和数据类型分组
        self.pools: Dict[Tuple[Tuple[int, ...], Any], List[MemoryBlock]] = defaultdict(list)
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_allocations': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'peak_usage_mb': 0.0
        }
        
        logger.info(f"CPU Memory Pool initialized, max size: {max_pool_size_mb}MB")
    
    def get_array(self, shape: Tuple[int, ...], dtype: np.dtype = np.float32) -> np.ndarray:
        """从内存池获取数组"""
        with self.lock:
            key = (shape, dtype)
            pool = self.pools[key]
            
            # 查找可用的内存块
            for block in pool:
                if not block.in_use:
                    block.in_use = True
                    block.last_used_time = time.time()
                    self.stats['pool_hits'] += 1
                    return block.array
            
            # 创建新的数组
            array = np.empty(shape, dtype=dtype)
            block = MemoryBlock(
                size=shape,
                dtype=dtype,
                device="cpu",
                array=array,
                in_use=True,
                created_time=time.time(),
                last_used_time=time.time()
            )
            
            pool.append(block)
            self.stats['pool_misses'] += 1
            self.stats['total_allocations'] += 1
            
            # 更新内存使用统计
            array_size = array.nbytes
            self.current_pool_size += array_size
            
            current_mb = self.current_pool_size / 1024 / 1024
            if current_mb > self.stats['peak_usage_mb']:
                self.stats['peak_usage_mb'] = current_mb
            
            return array
    
    def return_array(self, array: np.ndarray):
        """归还数组到内存池"""
        with self.lock:
            # 查找对应的内存块
            for pool in self.pools.values():
                for block in pool:
                    if block.array is array:
                        block.in_use = False
                        block.last_used_time = time.time()
                        return
            
            logger.warning("Attempted to return array not from pool")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取内存池统计信息"""
        with self.lock:
            total_blocks = sum(len(pool) for pool in self.pools.values())
            in_use_blocks = sum(1 for pool in self.pools.values() 
                              for block in pool if block.in_use)
            
            hit_rate = (self.stats['pool_hits'] / 
                       max(1, self.stats['pool_hits'] + self.stats['pool_misses']))
            
            return {
                'device': 'cpu',
                'total_blocks': total_blocks,
                'in_use_blocks': in_use_blocks,
                'current_size_mb': self.current_pool_size / 1024 / 1024,
                'peak_usage_mb': self.stats['peak_usage_mb'],
                'hit_rate': hit_rate,
                'total_allocations': self.stats['total_allocations'],
                'pool_hits': self.stats['pool_hits'],
                'pool_misses': self.stats['pool_misses']
            }

class MemoryManager:
    """统一内存管理器"""
    
    def __init__(self, gpu_pool_size_mb: int = 1024, cpu_pool_size_mb: int = 512):
        self.gpu_pool = GPUMemoryPool(max_pool_size_mb=gpu_pool_size_mb)
        self.cpu_pool = CPUMemoryPool(max_pool_size_mb=cpu_pool_size_mb)
        
        # 自动清理线程
        self.cleanup_thread = None
        self.cleanup_running = False
        self.start_cleanup_thread()
    
    def start_cleanup_thread(self):
        """启动自动清理线程"""
        if self.cleanup_running:
            return
        
        self.cleanup_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Memory cleanup thread started")
    
    def stop_cleanup_thread(self):
        """停止自动清理线程"""
        self.cleanup_running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5.0)
        logger.info("Memory cleanup thread stopped")
    
    def _cleanup_loop(self):
        """清理循环"""
        while self.cleanup_running:
            try:
                # 每5分钟清理一次
                time.sleep(300)
                
                # 清理GPU内存池
                self.gpu_pool._cleanup_unused_blocks()
                
                # 如果使用CUDA，清理缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
            except Exception as e:
                logger.error(f"Memory cleanup error: {e}")
    
    def get_gpu_tensor(self, shape: Tuple[int, ...], dtype: torch.dtype = torch.float32) -> torch.Tensor:
        """获取GPU张量"""
        return self.gpu_pool.get_tensor(shape, dtype)
    
    def return_gpu_tensor(self, tensor: torch.Tensor):
        """归还GPU张量"""
        self.gpu_pool.return_tensor(tensor)
    
    def get_cpu_array(self, shape: Tuple[int, ...], dtype: np.dtype = np.float32) -> np.ndarray:
        """获取CPU数组"""
        return self.cpu_pool.get_array(shape, dtype)
    
    def return_cpu_array(self, array: np.ndarray):
        """归还CPU数组"""
        self.cpu_pool.return_array(array)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取内存管理统计信息"""
        return {
            'gpu_pool': self.gpu_pool.get_stats(),
            'cpu_pool': self.cpu_pool.get_stats()
        }

# 全局内存管理器实例
_global_memory_manager: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    """获取全局内存管理器实例"""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager

def cleanup_memory_manager():
    """清理全局内存管理器"""
    global _global_memory_manager
    if _global_memory_manager is not None:
        _global_memory_manager.stop_cleanup_thread()
        _global_memory_manager = None

# 上下文管理器
class ManagedTensor:
    """托管张量上下文管理器"""
    
    def __init__(self, shape: Tuple[int, ...], dtype: torch.dtype = torch.float32):
        self.shape = shape
        self.dtype = dtype
        self.tensor = None
        self.manager = get_memory_manager()
    
    def __enter__(self) -> torch.Tensor:
        self.tensor = self.manager.get_gpu_tensor(self.shape, self.dtype)
        return self.tensor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tensor is not None:
            self.manager.return_gpu_tensor(self.tensor)

class ManagedArray:
    """托管数组上下文管理器"""
    
    def __init__(self, shape: Tuple[int, ...], dtype: np.dtype = np.float32):
        self.shape = shape
        self.dtype = dtype
        self.array = None
        self.manager = get_memory_manager()
    
    def __enter__(self) -> np.ndarray:
        self.array = self.manager.get_cpu_array(self.shape, self.dtype)
        return self.array
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.array is not None:
            self.manager.return_cpu_array(self.array) 