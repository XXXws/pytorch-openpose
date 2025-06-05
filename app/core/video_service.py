#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理服务模块（简化版）
基于demo_video.py的处理逻辑，提供异步视频处理功能
"""

import asyncio
import copy
import cv2
import numpy as np
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

# 导入现有的GPU优化模块
from src.body import Body
from src.hand import Hand
from src import util
from app.config import MODEL_DIR

# 导入FFmpeg工具
from app.core.ffmpeg_utils import (
    get_video_info_ffprobe, FFmpegWriter, 
    check_ffmpeg_available, check_ffprobe_available
)

class VideoTaskStatus:
    """视频任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

class VideoTask:
    """视频处理任务"""
    
    def __init__(self, task_id: str, input_file: str, output_file: str):
        self.task_id = task_id
        self.input_file = input_file
        self.output_file = output_file
        self.status = VideoTaskStatus.PENDING
        self.progress = 0.0
        self.total_frames = 0
        self.processed_frames = 0
        self.start_time = None
        self.end_time = None
        self.error_message = None
        self.video_info = {}
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "video_info": self.video_info
        }
        
        if self.start_time:
            result["start_time"] = self.start_time
            if self.end_time:
                result["processing_time"] = self.end_time - self.start_time
            else:
                result["elapsed_time"] = time.time() - self.start_time
                
        if self.error_message:
            result["error_message"] = self.error_message
            
        if self.status == VideoTaskStatus.COMPLETED:
            result["output_file"] = self.output_file
            
        return result

class VideoProcessingService:
    """视频处理服务类（简化版）"""
    
    def __init__(self):
        """初始化视频处理服务"""
        print("初始化视频处理服务...")
        
        # 检查FFmpeg可用性
        self.ffmpeg_available = check_ffmpeg_available()
        self.ffprobe_available = check_ffprobe_available()
        
        if not self.ffmpeg_available:
            print("警告: FFmpeg不可用，将使用OpenCV处理视频")
        if not self.ffprobe_available:
            print("警告: FFProbe不可用，将使用OpenCV获取视频信息")
        
        if self.ffmpeg_available and self.ffprobe_available:
            print("FFmpeg和FFProbe可用，将使用FFmpeg处理")
        
        # 初始化GPU优化的检测模型
        body_model_path = os.path.join(MODEL_DIR, 'body_pose_model.pth')
        hand_model_path = os.path.join(MODEL_DIR, 'hand_pose_model.pth')
        self.body_estimation = Body(body_model_path)
        self.hand_estimation = Hand(hand_model_path)
        
        # 任务存储
        self.tasks: Dict[str, VideoTask] = {}
        
        # 创建输出目录
        self.upload_dir = Path("uploads")
        self.result_dir = Path("results") 
        self.upload_dir.mkdir(exist_ok=True)
        self.result_dir.mkdir(exist_ok=True)
        
        # 重建任务状态（从现有文件恢复）
        self.rebuild_tasks_from_files()
        
        print("视频处理服务初始化完成")
    
    def get_video_info(self, file_path: str) -> Dict[str, Any]:
        """获取视频信息（优先使用FFProbe，回退到OpenCV）"""
        
        # 优先使用FFProbe获取视频信息
        if self.ffprobe_available:
            try:
                return get_video_info_ffprobe(file_path)
            except Exception as e:
                print(f"FFProbe失败，回退到OpenCV: {e}")
        
        # 回退到OpenCV方式
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise Exception("无法打开视频文件")
        
        # 获取基本信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return {
            "duration": duration,
            "fps": f"{int(fps)}/1",
            "fps_float": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "format_name": "mp4",  # OpenCV默认
            "codec_name": "unknown",
            "pix_fmt": "yuv420p",
            "bit_rate": 0,
            "size_bytes": 0
        }
    
    def process_frame(self, frame: np.ndarray, include_body: bool = True, include_hands: bool = True) -> np.ndarray:
        """处理单帧图像（复用demo_video.py的process_frame逻辑）"""
        canvas = copy.deepcopy(frame)
        candidate = None
        subset = None
        
        if include_body:
            candidate, subset = self.body_estimation(frame)
            canvas = util.draw_bodypose(canvas, candidate, subset)
            
        if include_hands and candidate is not None and subset is not None:
            hands_list = util.handDetect(candidate, subset, frame)
            all_hand_peaks = []
            
            for x, y, w, is_left in hands_list:
                try:
                    peaks = self.hand_estimation(frame[y:y+w, x:x+w, :])
                    peaks[:, 0] = np.where(peaks[:, 0] == 0, peaks[:, 0], peaks[:, 0] + x)
                    peaks[:, 1] = np.where(peaks[:, 1] == 0, peaks[:, 1], peaks[:, 1] + y)
                    all_hand_peaks.append(peaks)
                except Exception as e:
                    print(f"手部检测错误: {e}")
                    continue
                    
            canvas = util.draw_handpose(canvas, all_hand_peaks)
        
        return canvas
    
    def create_video_task(
        self, 
        input_file: str, 
        include_body: bool = True, 
        include_hands: bool = True
    ) -> str:
        """创建视频处理任务"""
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 生成输出文件路径
        input_path = Path(input_file)
        output_filename = f"{input_path.stem}_processed_{task_id[:8]}.mp4"
        output_file = str(self.result_dir / output_filename)
        
        # 创建任务对象
        task = VideoTask(task_id, input_file, output_file)
        
        # 获取视频信息
        try:
            video_info = self.get_video_info(input_file)
            task.video_info = video_info
            task.total_frames = video_info["frame_count"]
            
        except Exception as e:
            task.status = VideoTaskStatus.FAILED
            task.error_message = f"视频信息获取失败: {str(e)}"
            self.tasks[task_id] = task
            return task_id
        
        # 保存任务参数
        task.processing_params = {
            "include_body": include_body,
            "include_hands": include_hands
        }
        
        # 存储任务
        self.tasks[task_id] = task
        
        # 启动异步处理
        try:
            # 尝试在现有事件循环中创建任务
            asyncio.create_task(self._process_video_async(task))
        except RuntimeError:
            # 如果没有运行的事件循环，在新线程中启动
            import threading
            
            def run_async_task():
                asyncio.run(self._process_video_async(task))
            
            thread = threading.Thread(target=run_async_task, daemon=True)
            thread.start()
        
        return task_id
    
    async def _process_video_async(self, task: VideoTask):
        """异步处理视频（优先使用FFmpeg，回退到OpenCV）"""
        try:
            task.status = VideoTaskStatus.PROCESSING
            task.start_time = time.time()
            
            print(f"开始处理视频任务: {task.task_id}")
            
            # 打开输入视频
            cap = cv2.VideoCapture(task.input_file)
            if not cap.isOpened():
                raise Exception("无法打开输入视频文件")
            
            # 获取处理参数
            include_body = task.processing_params.get("include_body", True)
            include_hands = task.processing_params.get("include_hands", True)
            
            # 获取视频信息
            video_info = task.video_info
            
            # 初始化写入器（优先使用FFmpeg）
            writer = None
            use_ffmpeg = self.ffmpeg_available
            
            frame_count = 0
            
            # 处理每一帧
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    print(f"视频读取结束，共处理 {frame_count} 帧")
                    break
                
                # 验证帧数据
                if frame.size == 0:
                    print(f"警告: 第{frame_count + 1}帧为空，跳过")
                    continue
                
                # 处理帧
                try:
                    posed_frame = self.process_frame(frame, include_body, include_hands)
                    
                    # 验证处理后的帧
                    if posed_frame is None or posed_frame.size == 0:
                        print(f"警告: 第{frame_count + 1}帧处理后为空，使用原始帧")
                        posed_frame = frame
                        
                except Exception as process_error:
                    print(f"警告: 第{frame_count + 1}帧处理失败，使用原始帧: {process_error}")
                    posed_frame = frame
                
                # 初始化写入器（在第一帧时）
                if writer is None:
                    frame_height, frame_width = posed_frame.shape[:2]
                    print(f"初始化写入器: 帧尺寸 {frame_width}x{frame_height}")
                    
                    if use_ffmpeg:
                        try:
                            # 使用FFmpeg写入器
                            fps_str = video_info.get("fps", "30/1")
                            pix_fmt = video_info.get("pix_fmt", "yuv420p")
                            codec = video_info.get("codec_name", "libx264")
                            
                            print(f"尝试创建FFmpeg写入器: fps={fps_str}, pix_fmt={pix_fmt}, codec={codec}")
                            
                            writer = FFmpegWriter(
                                task.output_file,
                                fps_str,
                                (frame_height, frame_width),
                                pix_fmt,
                                codec
                            )
                            print(f"FFmpeg写入器创建成功: {fps_str} fps, {codec} codec")
                            
                        except Exception as e:
                            print(f"FFmpeg写入器创建失败，回退到OpenCV: {e}")
                            use_ffmpeg = False
                    
                    if not use_ffmpeg:
                        # 回退到OpenCV写入器
                        fps = video_info.get("fps_float", 30.0)
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        
                        print(f"尝试创建OpenCV写入器: fps={fps}, fourcc=mp4v")
                        
                        writer = cv2.VideoWriter(task.output_file, fourcc, fps, (frame_width, frame_height))
                        
                        if not writer.isOpened():
                            raise Exception("无法创建OpenCV视频写入器")
                        print(f"OpenCV写入器创建成功: {fps} fps")
                
                # 写入处理后的帧
                try:
                    if use_ffmpeg and hasattr(writer, 'write_frame'):
                        writer.write_frame(posed_frame)
                    else:
                        writer.write(posed_frame)
                except Exception as write_error:
                    print(f"帧写入失败 (帧{frame_count}): {write_error}")
                    
                    # 如果是FFmpeg写入失败，尝试回退到OpenCV
                    if use_ffmpeg:
                        print("FFmpeg写入失败，尝试回退到OpenCV写入器...")
                        
                        # 关闭FFmpeg写入器
                        try:
                            if hasattr(writer, 'close'):
                                writer.close()
                        except:
                            pass
                        
                        # 重新创建OpenCV写入器
                        try:
                            frame_height, frame_width = posed_frame.shape[:2]
                            fps = task.video_info.get("fps_float", 30.0)
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            writer = cv2.VideoWriter(task.output_file, fourcc, fps, (frame_width, frame_height))
                            
                            if not writer.isOpened():
                                raise Exception("无法创建OpenCV视频写入器")
                            
                            use_ffmpeg = False
                            print(f"已切换到OpenCV写入器: {fps} fps")
                            
                            # 重新写入当前帧
                            writer.write(posed_frame)
                            
                        except Exception as fallback_error:
                            raise Exception(f"FFmpeg和OpenCV写入器都失败: FFmpeg={write_error}, OpenCV={fallback_error}")
                    else:
                        # OpenCV写入失败，无法回退
                        raise Exception(f"OpenCV写入器失败: {write_error}")
                
                # 更新进度
                frame_count += 1
                task.processed_frames = frame_count
                if task.total_frames > 0:
                    task.progress = min(frame_count / task.total_frames * 100, 100.0)
                
                # 每处理5帧输出一次进度
                if frame_count % 5 == 0:
                    print(f"任务 {task.task_id[:8]} 进度: {task.progress:.1f}% ({frame_count}/{task.total_frames})")
                
                # 自适应性能调节
                try:
                    from app.core.performance_monitor import get_performance_monitor
                    monitor = get_performance_monitor()
                    recommendations = monitor.get_processing_recommendations()
                    
                    # 根据性能建议调整处理策略
                    sleep_interval = recommendations.get('sleep_interval', 0.005)
                    
                    # 更频繁地让出控制权，减少阻塞其他API
                    if frame_count % 2 == 0:
                        await asyncio.sleep(sleep_interval)
                    
                    # 每10帧进行更长的让步，确保其他API有足够时间响应
                    if frame_count % 10 == 0:
                        await asyncio.sleep(sleep_interval * 4)  # 4倍基础间隔
                        
                    # 如果系统资源紧张，额外增加让步
                    if recommendations.get('reason') and '紧张' in recommendations.get('reason', ''):
                        if frame_count % 5 == 0:
                            await asyncio.sleep(0.05)  # 额外50ms让步
                            
                except Exception as perf_error:
                    # 性能监控失败时使用默认策略
                    if frame_count % 2 == 0:
                        await asyncio.sleep(0.005)
                    if frame_count % 10 == 0:
                        await asyncio.sleep(0.02)
            
            # 清理资源
            cap.release()
            
            if writer is not None:
                if use_ffmpeg and hasattr(writer, 'close'):
                    writer.close()
                elif hasattr(writer, 'release'):
                    writer.release()
            
            # 验证输出文件
            if not self._validate_output_video(task.output_file):
                raise Exception("生成的视频文件无效或损坏")
            
            # 任务完成
            task.status = VideoTaskStatus.COMPLETED
            task.end_time = time.time()
            task.progress = 100.0
            
            processing_method = "FFmpeg" if use_ffmpeg else "OpenCV"
            print(f"视频任务完成: {task.task_id[:8]}, 使用{processing_method}, 耗时: {task.end_time - task.start_time:.2f}秒")
            
        except Exception as e:
            task.status = VideoTaskStatus.FAILED
            task.error_message = str(e)
            task.end_time = time.time()
            print(f"视频任务失败: {task.task_id[:8]}, 错误: {e}")
    
    def _validate_output_video(self, video_path: str) -> bool:
        """验证输出视频文件是否有效"""
        try:
            # 检查文件是否存在且不为空
            if not os.path.exists(video_path):
                print(f"验证失败: 文件不存在 {video_path}")
                return False
            
            file_size = os.path.getsize(video_path)
            if file_size < 1024:  # 文件小于1KB认为无效
                print(f"验证失败: 文件过小 {file_size} bytes")
                return False
            
            # 使用OpenCV验证视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"验证失败: OpenCV无法打开文件")
                cap.release()
                return False
            
            # 检查视频属性
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            cap.release()
            
            # 验证基本属性
            if frame_count <= 0 or fps <= 0 or width <= 0 or height <= 0:
                print(f"验证失败: 视频属性异常 - 帧数:{frame_count}, fps:{fps}, 尺寸:{width}x{height}")
                return False
            
            print(f"视频验证成功: {frame_count}帧, {fps}fps, {width}x{height}, {file_size}bytes")
            return True
            
        except Exception as e:
            print(f"验证失败: 验证过程出错 - {str(e)}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()
    
    def list_tasks(self) -> Dict[str, Any]:
        """列出所有任务"""
        return {
            "tasks": [task.to_dict() for task in self.tasks.values()],
            "total_count": len(self.tasks),
            "status_summary": {
                "pending": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.PENDING]),
                "processing": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.PROCESSING]),
                "completed": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.COMPLETED]),
                "failed": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.FAILED])
            }
        }
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        current_time = time.time()
        to_remove = []
        
        for task_id, task in self.tasks.items():
            if task.start_time and (current_time - task.start_time) > (max_age_hours * 3600):
                # 删除输出文件
                if os.path.exists(task.output_file):
                    try:
                        os.remove(task.output_file)
                    except:
                        pass
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        return len(to_remove)
    
    def rebuild_tasks_from_files(self):
        """从results目录中的文件重建任务状态"""
        try:
            print("开始重建任务状态...")
            
            # 扫描results目录
            if not self.result_dir.exists():
                print("results目录不存在，跳过任务重建")
                return
            
            rebuilt_count = 0
            
            # 查找所有处理过的视频文件
            for video_file in self.result_dir.glob("*_processed_*.mp4"):
                try:
                    # 解析文件名获取任务信息
                    filename = video_file.stem  # 去掉.mp4扩展名
                    
                    # 文件名格式: {original_name}_processed_{task_id_short}
                    if "_processed_" not in filename:
                        continue
                    
                    parts = filename.split("_processed_")
                    if len(parts) != 2:
                        continue
                    
                    original_name = parts[0]
                    task_id_short = parts[1]
                    
                    # 生成完整的任务ID（使用短ID作为前缀）
                    # 由于我们只有短ID，创建一个基于文件的伪任务ID
                    task_id = f"{task_id_short}-{int(video_file.stat().st_mtime)}"
                    
                    # 检查任务是否已存在
                    if task_id in self.tasks:
                        continue
                    
                    # 创建任务对象
                    task = VideoTask(task_id, "", str(video_file))
                    task.status = VideoTaskStatus.COMPLETED
                    task.progress = 100.0
                    
                    # 获取文件信息
                    file_stat = video_file.stat()
                    task.end_time = file_stat.st_mtime
                    task.start_time = file_stat.st_mtime - 300  # 假设处理时间5分钟
                    
                    # 获取视频信息
                    try:
                        video_info = self.get_video_info(str(video_file))
                        task.video_info = video_info
                        task.total_frames = video_info.get("frame_count", 0)
                        task.processed_frames = task.total_frames
                    except Exception as e:
                        print(f"获取视频信息失败 {video_file.name}: {e}")
                        # 使用默认值
                        task.video_info = {}
                        task.total_frames = 0
                        task.processed_frames = 0
                    
                    # 验证视频文件
                    if self._validate_output_video(str(video_file)):
                        self.tasks[task_id] = task
                        rebuilt_count += 1
                        print(f"重建任务: {task_id[:8]} -> {video_file.name}")
                    else:
                        print(f"跳过无效视频文件: {video_file.name}")
                        
                except Exception as e:
                    print(f"重建任务失败 {video_file.name}: {e}")
                    continue
            
            print(f"任务重建完成，共重建 {rebuilt_count} 个任务")
            
        except Exception as e:
            print(f"任务重建过程出错: {e}")

# 全局视频处理服务实例
_video_service: Optional[VideoProcessingService] = None

def get_video_service() -> VideoProcessingService:
    """获取视频处理服务单例"""
    global _video_service
    if _video_service is None:
        _video_service = VideoProcessingService()
    return _video_service 