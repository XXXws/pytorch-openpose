#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Video task manager handling asynchronous processing."""

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import cv2
import numpy as np

from app.core.video_service import get_video_service
from app.core.ffmpeg_utils import (
    get_video_info_ffprobe, FFmpegWriter,
    check_ffmpeg_available, check_ffprobe_available,
)


class VideoTaskStatus:
    """Simple task status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoTask:
    """Data holder for video processing task."""

    def __init__(self, task_id: str, input_file: str, output_file: str):
        self.task_id = task_id
        self.input_file = input_file
        self.output_file = output_file
        self.status = VideoTaskStatus.PENDING
        self.progress = 0.0
        self.total_frames = 0
        self.processed_frames = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.video_info: Dict[str, Any] = {}
        self.processing_params: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "video_info": self.video_info,
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


class VideoTaskManager:
    """Manager dealing with task lifecycle and processing."""

    def __init__(self):
        self.ffmpeg_available = check_ffmpeg_available()
        self.ffprobe_available = check_ffprobe_available()
        self.tasks: Dict[str, VideoTask] = {}
        self.upload_dir = Path("uploads")
        self.result_dir = Path("results")
        self.upload_dir.mkdir(exist_ok=True)
        self.result_dir.mkdir(exist_ok=True)
        self.rebuild_tasks_from_files()

    def get_video_info(self, file_path: str) -> Dict[str, Any]:
        if self.ffprobe_available:
            try:
                return get_video_info_ffprobe(file_path)
            except Exception:
                pass
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise Exception("无法打开视频文件")
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
            "format_name": "mp4",
            "codec_name": "unknown",
            "pix_fmt": "yuv420p",
            "bit_rate": 0,
            "size_bytes": 0,
        }

    def create_video_task(self, input_file: str, include_body: bool = True, include_hands: bool = True) -> str:
        task_id = str(uuid.uuid4())
        input_path = Path(input_file)
        output_filename = f"{input_path.stem}_processed_{task_id[:8]}.mp4"
        output_file = str(self.result_dir / output_filename)
        task = VideoTask(task_id, input_file, output_file)
        try:
            info = self.get_video_info(input_file)
            task.video_info = info
            task.total_frames = info.get("frame_count", 0)
        except Exception as e:
            task.status = VideoTaskStatus.FAILED
            task.error_message = f"视频信息获取失败: {str(e)}"
            self.tasks[task_id] = task
            return task_id
        task.processing_params = {
            "include_body": include_body,
            "include_hands": include_hands,
        }
        self.tasks[task_id] = task
        try:
            asyncio.create_task(self._process_video_async(task))
        except RuntimeError:
            import threading

            def run_async():
                asyncio.run(self._process_video_async(task))

            t = threading.Thread(target=run_async, daemon=True)
            t.start()
        return task_id

    async def _process_video_async(self, task: VideoTask):
        try:
            task.status = VideoTaskStatus.PROCESSING
            task.start_time = time.time()
            cap = cv2.VideoCapture(task.input_file)
            if not cap.isOpened():
                raise Exception("无法打开输入视频文件")
            include_body = task.processing_params.get("include_body", True)
            include_hands = task.processing_params.get("include_hands", True)
            video_service = get_video_service()
            video_info = task.video_info
            writer = None
            use_ffmpeg = self.ffmpeg_available
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                if frame.size == 0:
                    continue
                posed = video_service.process_frame(frame, include_body, include_hands)
                if posed is None or posed.size == 0:
                    posed = frame
                if writer is None:
                    h, w = posed.shape[:2]
                    if use_ffmpeg:
                        try:
                            fps_str = video_info.get("fps", "30/1")
                            pix_fmt = video_info.get("pix_fmt", "yuv420p")
                            codec = video_info.get("codec_name", "libx264")
                            writer = FFmpegWriter(
                                task.output_file,
                                fps_str,
                                (h, w),
                                pix_fmt,
                                codec,
                            )
                        except Exception:
                            use_ffmpeg = False
                    if not use_ffmpeg:
                        fps = video_info.get("fps_float", 30.0)
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        writer = cv2.VideoWriter(task.output_file, fourcc, fps, (w, h))
                        if not writer.isOpened():
                            raise Exception("无法创建OpenCV视频写入器")
                try:
                    if use_ffmpeg and hasattr(writer, "write_frame"):
                        writer.write_frame(posed)
                    else:
                        writer.write(posed)
                except Exception as err:
                    if use_ffmpeg:
                        try:
                            if hasattr(writer, "close"):
                                writer.close()
                        except Exception:
                            pass
                        fps = video_info.get("fps_float", 30.0)
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        writer = cv2.VideoWriter(task.output_file, fourcc, fps, (w, h))
                        if not writer.isOpened():
                            raise Exception("无法创建OpenCV视频写入器")
                        use_ffmpeg = False
                        writer.write(posed)
                    else:
                        raise Exception(f"OpenCV写入失败: {err}")
                frame_count += 1
                task.processed_frames = frame_count
                if task.total_frames > 0:
                    task.progress = min(frame_count / task.total_frames * 100, 100.0)
                if frame_count % 5 == 0:
                    await asyncio.sleep(0)
            cap.release()
            if writer is not None:
                if use_ffmpeg and hasattr(writer, "close"):
                    writer.close()
                elif hasattr(writer, "release"):
                    writer.release()
            if not self._validate_output_video(task.output_file):
                raise Exception("生成的视频文件无效或损坏")
            task.status = VideoTaskStatus.COMPLETED
            task.end_time = time.time()
            task.progress = 100.0
        except Exception as e:
            task.status = VideoTaskStatus.FAILED
            task.error_message = str(e)
            task.end_time = time.time()

    def _validate_output_video(self, video_path: str) -> bool:
        try:
            if not os.path.exists(video_path):
                return False
            file_size = os.path.getsize(video_path)
            if file_size < 1024:
                return False
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                cap.release()
                return False
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if frame_count <= 0 or fps <= 0 or width <= 0 or height <= 0:
                return False
            return True
        except Exception:
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()

    def list_tasks(self) -> Dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "total_count": len(self.tasks),
            "status_summary": {
                "pending": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.PENDING]),
                "processing": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.PROCESSING]),
                "completed": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.COMPLETED]),
                "failed": len([t for t in self.tasks.values() if t.status == VideoTaskStatus.FAILED]),
            },
        }

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        current_time = time.time()
        to_remove = []
        for tid, task in list(self.tasks.items()):
            if task.start_time and (current_time - task.start_time) > (max_age_hours * 3600):
                if os.path.exists(task.output_file):
                    try:
                        os.remove(task.output_file)
                    except Exception:
                        pass
                to_remove.append(tid)
        for tid in to_remove:
            del self.tasks[tid]
        return len(to_remove)

    def rebuild_tasks_from_files(self):
        try:
            if not self.result_dir.exists():
                return
            for video_file in self.result_dir.glob("*_processed_*.mp4"):
                filename = video_file.stem
                if "_processed_" not in filename:
                    continue
                parts = filename.split("_processed_")
                if len(parts) != 2:
                    continue
                task_id = f"{parts[1]}-{int(video_file.stat().st_mtime)}"
                if task_id in self.tasks:
                    continue
                task = VideoTask(task_id, "", str(video_file))
                task.status = VideoTaskStatus.COMPLETED
                task.progress = 100.0
                task.end_time = video_file.stat().st_mtime
                task.start_time = task.end_time - 300
                try:
                    info = self.get_video_info(str(video_file))
                    task.video_info = info
                    task.total_frames = info.get("frame_count", 0)
                    task.processed_frames = task.total_frames
                except Exception:
                    pass
                if self._validate_output_video(str(video_file)):
                    self.tasks[task_id] = task
        except Exception:
            pass


_task_manager: Optional[VideoTaskManager] = None
_task_manager_lock = asyncio.Lock()


def get_video_task_manager() -> VideoTaskManager:
    global _task_manager
    if _task_manager is None:
        import threading
        with threading.Lock():
            if _task_manager is None:
                _task_manager = VideoTaskManager()
    return _task_manager
