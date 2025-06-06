#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频处理API路由
实现视频上传、异步处理、任务状态查询和结果获取
"""

import os
import tempfile
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.video_task_manager import (
    get_video_task_manager,
    VideoTaskStatus,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["视频处理"])

# Pydantic模型定义
class VideoUploadRequest(BaseModel):
    """视频上传请求模型"""
    include_body: bool = True
    include_hands: bool = True

class TaskStatusResponse(BaseModel):
    """任务状态响应模型"""
    task_id: str
    status: str
    progress: float
    total_frames: int
    processed_frames: int
    video_info: Dict[str, Any]
    start_time: Optional[float] = None
    processing_time: Optional[float] = None
    elapsed_time: Optional[float] = None
    error_message: Optional[str] = None
    output_file: Optional[str] = None

@router.post("/upload", summary="上传视频文件并创建处理任务")
async def upload_video(
    file: UploadFile = File(..., description="视频文件"),
    include_body: bool = Form(True, description="是否检测身体姿态"),
    include_hands: bool = Form(True, description="是否检测手部姿态")
) -> Dict[str, Any]:
    """
    上传视频文件并创建异步处理任务
    
    - **file**: 视频文件（支持常见格式：mp4, avi, mov, mkv等）
    - **include_body**: 是否进行身体姿态检测
    - **include_hands**: 是否进行手部姿态检测
    
    返回任务ID，用于后续查询处理状态
    """
    
    try:
        logger.info(f"收到视频上传请求: {file.filename}")
        logger.info(f"文件类型: {file.content_type}")
        logger.info(f"检测选项: body={include_body}, hands={include_hands}")
        
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('video/'):
            logger.error(f"文件类型验证失败: {file.content_type}")
            raise HTTPException(status_code=400, detail="请上传视频文件")
        
        # 验证文件大小（限制100MB）
        file_size = 0
        temp_content = await file.read()
        file_size = len(temp_content)
        await file.seek(0)  # 重置文件指针
        
        logger.info(f"文件大小: {file_size / 1024 / 1024:.2f}MB")
        
        if file_size > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(status_code=400, detail="文件大小不能超过100MB")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="文件为空")
        
        # 创建临时文件存储上传的视频
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(exist_ok=True)
        logger.info(f"上传目录已创建: {upload_dir}")
        
        # 生成唯一文件名
        timestamp = int(time.time())
        file_suffix = Path(file.filename).suffix.lower()
        if not file_suffix:
            file_suffix = '.mp4'
        
        temp_filename = f"video_{timestamp}_{hash(file.filename) % 10000}{file_suffix}"
        temp_file_path = upload_dir / temp_filename
        logger.info(f"临时文件路径: {temp_file_path}")
        
        # 保存上传文件
        with open(temp_file_path, "wb") as temp_file:
            await file.seek(0)
            content = await file.read()
            temp_file.write(content)
        logger.info(f"文件保存成功: {temp_file_path}")
        
        # 获取任务管理器并创建任务
        logger.info("正在获取视频任务管理器...")
        try:
            task_manager = get_video_task_manager()
            logger.info("任务管理器获取成功")
        except Exception as e:
            logger.error(f"任务管理器获取失败: {e}")
            raise HTTPException(status_code=500, detail=f"任务管理器初始化失败: {str(e)}")

        logger.info("正在创建视频处理任务...")
        try:
            task_id = task_manager.create_video_task(
                str(temp_file_path),
                include_body=include_body,
                include_hands=include_hands
            )
            logger.info(f"任务创建成功: {task_id}")
        except Exception as e:
            logger.error(f"任务创建失败: {e}")
            # 清理临时文件
            if temp_file_path.exists():
                temp_file_path.unlink()
            raise HTTPException(status_code=500, detail=f"任务创建失败: {str(e)}")
        
        return {
            "success": True,
            "message": "视频上传成功，处理任务已创建",
            "task_id": task_id,
            "file_info": {
                "filename": file.filename,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "temp_path": str(temp_file_path)
            },
            "processing_options": {
                "include_body": include_body,
                "include_hands": include_hands
            }
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 捕获所有其他异常
        logger.exception(f"视频上传异常: {str(e)}")
        
        # 清理临时文件
        if 'temp_file_path' in locals() and temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass
        
        raise HTTPException(status_code=500, detail=f"视频上传失败: {str(e)}")

@router.get("/task/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    查询视频处理任务状态
    
    - **task_id**: 任务ID
    
    返回任务的详细状态信息，包括处理进度
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskStatusResponse(**task_status)

@router.get("/tasks", summary="获取所有任务列表")
async def list_tasks() -> Dict[str, Any]:
    """
    获取所有视频处理任务的列表和统计信息
    
    返回任务列表和状态统计
    """
    
    task_manager = get_video_task_manager()
    return task_manager.list_tasks()

@router.get("/task/{task_id}/result", summary="下载处理结果")
async def download_result(task_id: str):
    """
    下载处理完成的视频文件
    
    - **task_id**: 任务ID
    
    返回处理后的视频文件
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task_status["status"] != VideoTaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"任务尚未完成，当前状态: {task_status['status']}"
        )
    
    output_file = task_status.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="结果文件不存在")
    
    # 生成下载文件名
    original_name = Path(output_file).stem
    download_filename = f"{original_name}_openpose_result.mp4"
    
    return FileResponse(
        path=output_file,
        filename=download_filename,
        media_type='video/mp4',
        headers={
            "Content-Disposition": f"attachment; filename={download_filename}",
            # CORS头，解决跨域访问问题
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@router.api_route("/task/{task_id}/play", methods=["GET", "HEAD"], summary="播放处理结果")
async def play_result(task_id: str, request: Request = None):
    """
    播放处理完成的视频文件（用于在线播放）
    
    - **task_id**: 任务ID
    
    返回可在浏览器中直接播放的视频文件
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_status["status"] != VideoTaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"任务尚未完成，当前状态: {task_status['status']}"
        )

    output_file = task_status.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="结果文件不存在")
    
    # 验证视频文件完整性
    try:
        import cv2
        cap = cv2.VideoCapture(output_file)
        if not cap.isOpened():
            cap.release()
            raise HTTPException(status_code=500, detail="视频文件损坏，无法播放")
        
        # 检查基本属性
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        if frame_count <= 0 or fps <= 0 or width <= 0 or height <= 0:
            raise HTTPException(status_code=500, detail="视频文件属性异常，无法播放")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频文件验证失败: {str(e)}")

    # 获取文件大小用于Content-Length
    file_size = os.path.getsize(output_file)
    
    # 构建响应头
    headers = {
        "Cache-Control": "public, max-age=3600",  # 缓存1小时
        "Accept-Ranges": "bytes",  # 支持Range请求，用于视频流播放
        "Content-Length": str(file_size),  # 明确指定文件大小
        "Content-Disposition": "inline",  # 明确指定为内联显示
        # CORS头，解决跨域访问问题
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Expose-Headers": "Content-Length, Accept-Ranges"
    }
    
    # 如果是HEAD请求，只返回头信息
    if request and request.method == "HEAD":
        from fastapi.responses import Response
        return Response(
            content="",
            media_type='video/mp4',
            headers=headers
        )
    
    # 返回用于播放的视频文件（不强制下载）
    return FileResponse(
        path=output_file,
        media_type='video/mp4',
        headers=headers
    )

@router.get("/task/{task_id}/info", summary="获取任务详细信息")
async def get_task_info(task_id: str) -> Dict[str, Any]:
    """
    获取任务的详细信息，包括视频元数据
    
    - **task_id**: 任务ID
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_info": task_status,
        "video_metadata": task_status.get("video_info", {}),
        "processing_summary": {
            "total_frames": task_status.get("total_frames", 0),
            "processed_frames": task_status.get("processed_frames", 0),
            "progress_percentage": task_status.get("progress", 0),
            "estimated_remaining_time": _calculate_remaining_time(task_status)
        }
    }

@router.delete("/task/{task_id}", summary="删除任务")
async def delete_task(task_id: str) -> Dict[str, Any]:
    """
    删除指定的视频处理任务
    
    - **task_id**: 任务ID
    
    注意：只能删除已完成或失败的任务
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task_status["status"] == VideoTaskStatus.PROCESSING:
        raise HTTPException(status_code=400, detail="无法删除正在处理的任务")
    
    # 删除输出文件
    output_file = task_status.get("output_file")
    if output_file and os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception as e:
            logger.error(f"删除输出文件失败: {e}")
    
    # 从任务列表中移除
    task_manager = get_video_task_manager()
    if hasattr(task_manager, 'tasks') and task_id in task_manager.tasks:
        del task_manager.tasks[task_id]
    
    return {
        "success": True,
        "message": f"任务 {task_id} 已删除",
        "task_id": task_id
    }

@router.post("/cleanup", summary="清理旧任务")
async def cleanup_tasks(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    清理指定时间之前的旧任务
    
    - **max_age_hours**: 任务最大保留时间（小时），默认24小时
    """
    
    task_manager = get_video_task_manager()
    cleaned_count = task_manager.cleanup_old_tasks(max_age_hours)
    
    return {
        "success": True,
        "message": f"已清理 {cleaned_count} 个旧任务",
        "cleaned_count": cleaned_count,
        "max_age_hours": max_age_hours
    }

@router.get("/stats", summary="获取处理统计")
async def get_processing_stats() -> Dict[str, Any]:
    """
    获取视频处理服务的统计信息
    """
    
    task_manager = get_video_task_manager()
    all_tasks = task_manager.list_tasks()
    
    # 计算各种统计信息
    stats = {
        "总任务数": all_tasks["total_count"],
        "状态分布": all_tasks["status_summary"],
        "平均处理时间": 0,
        "成功率": 0
    }
    
    # 计算平均处理时间和成功率
    completed_tasks = [
        task for task in all_tasks["tasks"] 
        if task["status"] == VideoTaskStatus.COMPLETED and "processing_time" in task
    ]
    
    if completed_tasks:
        avg_time = sum(task["processing_time"] for task in completed_tasks) / len(completed_tasks)
        stats["平均处理时间"] = round(avg_time, 2)
        stats["成功率"] = round(len(completed_tasks) / all_tasks["total_count"] * 100, 1)
    
    return stats

def _calculate_remaining_time(task_status: Dict[str, Any]) -> Optional[float]:
    """计算预估剩余时间"""
    if task_status.get("status") != VideoTaskStatus.PROCESSING:
        return None
    
    progress = task_status.get("progress", 0)
    elapsed_time = task_status.get("elapsed_time", 0)
    
    if progress > 0 and elapsed_time > 0:
        total_estimated_time = elapsed_time / (progress / 100)
        remaining_time = total_estimated_time - elapsed_time
        return max(0, round(remaining_time, 1))
    
    return None

@router.post("/task/{task_id}/pause", summary="暂停视频处理任务")
async def pause_task(task_id: str) -> Dict[str, Any]:
    """
    暂停正在处理的视频任务
    
    - **task_id**: 任务ID
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task_status["status"] != VideoTaskStatus.PROCESSING:
        raise HTTPException(
            status_code=400, 
            detail=f"只能暂停正在处理的任务，当前状态: {task_status['status']}"
        )
    
    # 设置暂停标志（简化实现）
    if hasattr(task_manager, 'tasks') and task_id in task_manager.tasks:
        task = task_manager.tasks[task_id]
        task.status = "paused"  # 添加暂停状态
        
        return {
            "success": True,
            "message": f"任务 {task_id} 已暂停",
            "task_id": task_id,
            "paused_at_progress": task_status.get("progress", 0)
        }
    
    raise HTTPException(status_code=500, detail="暂停任务失败")

@router.post("/task/{task_id}/resume", summary="恢复视频处理任务")
async def resume_task(task_id: str) -> Dict[str, Any]:
    """
    恢复已暂停的视频任务
    
    - **task_id**: 任务ID
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task_status["status"] != "paused":
        raise HTTPException(
            status_code=400, 
            detail=f"只能恢复已暂停的任务，当前状态: {task_status['status']}"
        )
    
    # 恢复处理（简化实现）
    if hasattr(task_manager, 'tasks') and task_id in task_manager.tasks:
        task = task_manager.tasks[task_id]
        task.status = VideoTaskStatus.PROCESSING
        
        return {
            "success": True,
            "message": f"任务 {task_id} 已恢复",
            "task_id": task_id,
            "resume_from_progress": task_status.get("progress", 0)
        }
    
    raise HTTPException(status_code=500, detail="恢复任务失败")

@router.get("/task/{task_id}/preview", summary="获取视频处理预览")
async def get_task_preview(task_id: str) -> Dict[str, Any]:
    """
    获取视频处理的预览信息，包括关键帧检测结果
    
    - **task_id**: 任务ID
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 生成预览信息
    preview_info = {
        "task_id": task_id,
        "status": task_status["status"],
        "video_metadata": task_status.get("video_info", {}),
        "processing_stats": {
            "total_frames": task_status.get("total_frames", 0),
            "processed_frames": task_status.get("processed_frames", 0),
            "progress_percentage": task_status.get("progress", 0),
            "estimated_remaining_time": _calculate_remaining_time(task_status)
        }
    }
    
    # 如果任务完成，添加结果文件信息
    if task_status["status"] == VideoTaskStatus.COMPLETED:
        output_file = task_status.get("output_file")
        if output_file and os.path.exists(output_file):
            file_stat = os.stat(output_file)
            preview_info["result_file"] = {
                "filename": os.path.basename(output_file),
                "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                "download_url": f"/api/video/task/{task_id}/result"
            }
    
    return preview_info

@router.get("/task/{task_id}/log", summary="获取任务处理日志")
async def get_task_log(task_id: str) -> Dict[str, Any]:
    """
    获取视频处理任务的详细日志
    
    - **task_id**: 任务ID
    """
    
    task_manager = get_video_task_manager()
    task_status = task_manager.get_task_status(task_id)
    
    if task_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 构建处理日志
    log_entries = []
    
    if task_status.get("start_time"):
        log_entries.append({
            "timestamp": task_status["start_time"],
            "event": "任务开始",
            "message": f"开始处理视频，总帧数: {task_status.get('total_frames', 0)}"
        })
    
    # 添加进度日志
    if task_status.get("processed_frames", 0) > 0:
        log_entries.append({
            "timestamp": time.time(),
            "event": "处理进度",
            "message": f"已处理 {task_status['processed_frames']} / {task_status.get('total_frames', 0)} 帧 ({task_status.get('progress', 0):.1f}%)"
        })
    
    # 添加完成或错误日志
    if task_status["status"] == VideoTaskStatus.COMPLETED:
        log_entries.append({
            "timestamp": task_status.get("end_time", time.time()),
            "event": "任务完成",
            "message": f"视频处理成功完成，耗时: {task_status.get('processing_time', 0):.2f}秒"
        })
    elif task_status["status"] == VideoTaskStatus.FAILED:
        log_entries.append({
            "timestamp": task_status.get("end_time", time.time()),
            "event": "任务失败",
            "message": task_status.get("error_message", "未知错误")
        })
    
    return {
        "task_id": task_id,
        "log_entries": log_entries,
        "total_entries": len(log_entries)
    }

@router.api_route("/file/{filename}", methods=["GET", "HEAD"], summary="直接访问视频文件")
async def get_video_file(filename: str, request: Request = None):
    """
    直接通过文件名访问视频文件（备用访问方式）
    
    - **filename**: 视频文件名
    
    用于当任务状态丢失时的备用访问方式
    """
    
    # 安全检查：只允许访问results目录中的mp4文件
    if not filename.endswith('.mp4') or '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    # 构建文件路径
    file_path = os.path.join(settings.result_dir, filename)

    logger.info(f"尝试访问视频文件: {filename}")
    logger.debug(f"完整文件路径: {file_path}")
    logger.debug(f"文件是否存在: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在错误: {file_path}")
        # 列出results目录中的所有文件用于调试
        try:
            results_files = os.listdir(settings.result_dir)
            logger.debug(f"results目录中的文件: {results_files}")
        except Exception as e:
            logger.error(f"无法列出results目录: {e}")
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 验证是否为有效的视频文件
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            cap.release()
            raise HTTPException(status_code=500, detail="视频文件损坏，无法播放")
        
        # 检查基本属性
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        if frame_count <= 0 or fps <= 0 or width <= 0 or height <= 0:
            raise HTTPException(status_code=500, detail="视频文件属性异常，无法播放")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频文件验证失败: {str(e)}")

    # 获取文件大小
    file_size = os.path.getsize(file_path)
    
    # 构建响应头
    headers = {
        "Cache-Control": "public, max-age=3600",
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Disposition": "inline",
        # CORS头
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Expose-Headers": "Content-Length, Accept-Ranges"
    }
    
    # 如果是HEAD请求，只返回头信息
    if request and request.method == "HEAD":
        from fastapi.responses import Response
        return Response(
            content="",
            media_type='video/mp4',
            headers=headers
        )
    
    # 返回视频文件
    return FileResponse(
        path=file_path,
        media_type='video/mp4',
        headers=headers
    ) 
