#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg工具模块
移植demo_video.py中的FFProbe和Writer实现，支持异步视频处理
"""

import json
import os
import subprocess
import ffmpeg
from typing import NamedTuple, Dict, Any, Tuple
from pathlib import Path


class FFProbeResult(NamedTuple):
    """FFProbe执行结果"""
    return_code: int
    json: str
    error: str


class FFmpegWriter:
    """FFmpeg视频写入器（基于demo_video.py的Writer类）"""
    
    def __init__(self, output_file: str, input_fps: str, input_framesize: Tuple[int, int], 
                 input_pix_fmt: str = "yuv420p", input_vcodec: str = "libx264"):
        """
        初始化FFmpeg写入器
        
        Args:
            output_file: 输出文件路径
            input_fps: 输入帧率
            input_framesize: 输入帧尺寸 (height, width)
            input_pix_fmt: 像素格式
            input_vcodec: 视频编解码器
        """
        self.output_file = output_file
        self.input_fps = input_fps
        self.input_framesize = input_framesize
        self.input_pix_fmt = input_pix_fmt
        self.input_vcodec = input_vcodec
        self.ff_proc = None
        self._closed = False
        
        # 如果输出文件已存在，先删除
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # 创建FFmpeg进程
        self._create_ffmpeg_process()
    
    def _create_ffmpeg_process(self):
        """创建FFmpeg处理进程"""
        try:
            # 解析帧率
            if "/" in self.input_fps:
                fps_parts = self.input_fps.split("/")
                fps_value = float(fps_parts[0]) / float(fps_parts[1]) if float(fps_parts[1]) != 0 else 30.0
            else:
                fps_value = float(self.input_fps)
            
            # 确保帧率合理
            if fps_value <= 0 or fps_value > 120:
                fps_value = 30.0
                print(f"警告: 帧率异常，使用默认值30fps")
            
            # 使用更兼容的编码器设置
            width, height = self.input_framesize[1], self.input_framesize[0]
            
            # 确保尺寸是偶数（H.264要求）
            if width % 2 != 0:
                width += 1
            if height % 2 != 0:
                height += 1
            
            print(f"FFmpeg参数: {width}x{height}, {fps_value}fps, {self.input_vcodec}")
            
            self.ff_proc = (
                ffmpeg
                .input('pipe:',
                       format='rawvideo',
                       pix_fmt="bgr24",  # OpenCV使用BGR格式
                       s=f'{width}x{height}',  # width x height
                       r=fps_value)
                .output(self.output_file, 
                       pix_fmt='yuv420p',  # 强制使用yuv420p，最兼容的像素格式
                       vcodec='libx264',   # 强制使用H.264编码器
                       preset='medium',    # 使用medium预设，平衡速度和兼容性
                       crf=23,            # 使用更高质量设置
                       profile='baseline', # 使用baseline profile，最大兼容性
                       level='3.1',       # 使用3.1级别，广泛支持
                       **{
                           'movflags': '+faststart',  # 优化MP4文件结构，支持流式播放
                           'pix_fmt': 'yuv420p',      # 再次确保像素格式
                           'strict': 'experimental'   # 允许实验性功能
                       })
                .overwrite_output()
                .run_async(pipe_stdin=True, pipe_stdout=subprocess.PIPE, pipe_stderr=subprocess.PIPE)
            )
            
            # 更新实际使用的帧尺寸
            self.input_framesize = (height, width)
            
        except Exception as e:
            raise Exception(f"创建FFmpeg进程失败: {str(e)}")
    
    def write_frame(self, frame):
        """写入一帧"""
        if self._closed or self.ff_proc is None:
            raise Exception("Writer已关闭或未初始化")
        
        # 检查FFmpeg进程状态
        if self.ff_proc.poll() is not None:
            # 进程已结束，获取错误信息
            try:
                stdout, stderr = self.ff_proc.communicate(timeout=1)
                error_msg = stderr.decode() if stderr else "FFmpeg进程意外终止"
                raise Exception(f"FFmpeg进程已终止: {error_msg}")
            except:
                raise Exception("FFmpeg进程已终止，无法获取错误信息")
        
        # 验证帧数据
        if frame is None:
            raise Exception("帧数据为空")
        
        # 确保帧数据是连续的numpy数组
        if not frame.flags['C_CONTIGUOUS']:
            frame = frame.copy()
        
        # 验证帧尺寸
        expected_height, expected_width = self.input_framesize
        actual_height, actual_width = frame.shape[:2]
        
        if actual_height != expected_height or actual_width != expected_width:
            raise Exception(f"帧尺寸不匹配: 期望{expected_width}x{expected_height}, 实际{actual_width}x{actual_height}")
        
        # 确保帧数据类型正确
        if frame.dtype != 'uint8':
            frame = frame.astype('uint8')
        
        try:
            # 写入帧数据
            frame_bytes = frame.tobytes()
            self.ff_proc.stdin.write(frame_bytes)
            self.ff_proc.stdin.flush()  # 确保数据被写入
            
        except BrokenPipeError:
            # 管道断开，获取FFmpeg错误信息
            try:
                stdout, stderr = self.ff_proc.communicate(timeout=1)
                error_msg = stderr.decode() if stderr else "管道断开"
                raise Exception(f"FFmpeg管道断开: {error_msg}")
            except:
                raise Exception("FFmpeg管道断开，无法获取错误信息")
        except Exception as e:
            raise Exception(f"写入帧失败: {str(e)}")
    
    def close(self):
        """关闭写入器"""
        if self._closed or self.ff_proc is None:
            return
        
        try:
            self.ff_proc.stdin.close()
            stdout, stderr = self.ff_proc.communicate(timeout=30)
            
            if self.ff_proc.returncode != 0:
                error_msg = stderr.decode() if stderr else "未知错误"
                print(f"FFmpeg处理警告: {error_msg}")
            
            self._closed = True
            
        except subprocess.TimeoutExpired:
            print("FFmpeg进程超时，强制终止")
            self.ff_proc.kill()
            self._closed = True
        except Exception as e:
            print(f"关闭FFmpeg进程时出错: {str(e)}")
            self._closed = True


def ffprobe(file_path: str) -> FFProbeResult:
    """
    使用FFProbe获取视频文件信息（移植自demo_video.py）
    
    Args:
        file_path: 视频文件路径
        
    Returns:
        FFProbeResult: 包含返回码、JSON数据和错误信息
    """
    command_array = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    
    try:
        result = subprocess.run(
            command_array, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            universal_newlines=True,
            timeout=30
        )
        return FFProbeResult(
            return_code=result.returncode,
            json=result.stdout,
            error=result.stderr
        )
    except subprocess.TimeoutExpired:
        return FFProbeResult(
            return_code=-1,
            json="",
            error="FFProbe执行超时"
        )
    except Exception as e:
        return FFProbeResult(
            return_code=-1,
            json="",
            error=f"FFProbe执行失败: {str(e)}"
        )


def get_video_info_ffprobe(file_path: str) -> Dict[str, Any]:
    """
    使用FFProbe获取详细的视频信息
    
    Args:
        file_path: 视频文件路径
        
    Returns:
        Dict: 包含视频元数据的字典
    """
    ffprobe_result = ffprobe(file_path)
    
    if ffprobe_result.return_code != 0:
        raise Exception(f"FFProbe失败: {ffprobe_result.error}")
    
    try:
        info = json.loads(ffprobe_result.json)
        
        # 获取视频流信息
        video_streams = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
        if not video_streams:
            raise Exception("未找到视频流")
        
        video_info = video_streams[0]
        format_info = info["format"]
        
        # 解析帧率
        fps_str = video_info.get("avg_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(fps_str)
        
        # 计算总帧数和时长
        duration = float(format_info.get("duration", 0))
        frame_count = int(video_info.get("nb_frames", 0))
        if frame_count == 0 and duration > 0:
            frame_count = int(duration * fps)
        
        return {
            "duration": duration,
            "fps": fps_str,
            "fps_float": fps,
            "width": int(video_info["width"]),
            "height": int(video_info["height"]),
            "frame_count": frame_count,
            "format_name": format_info["format_name"],
            "codec_name": video_info["codec_name"],
            "pix_fmt": video_info.get("pix_fmt", "yuv420p"),
            "bit_rate": int(format_info.get("bit_rate", 0)),
            "size_bytes": int(format_info.get("size", 0))
        }
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise Exception(f"解析FFProbe输出失败: {str(e)}")


def check_ffmpeg_available() -> bool:
    """检查FFmpeg是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False


def check_ffprobe_available() -> bool:
    """检查FFProbe是否可用"""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False 