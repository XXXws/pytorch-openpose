#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时检测WebSocket API
基于demo_camera.py的实时处理逻辑，提供WebSocket接口
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import cv2
import numpy as np
import json
import time
import base64
import asyncio
from typing import Dict, Any
import traceback

# 导入检测服务
from app.core.detection_service import get_detection_service

router = APIRouter()

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_stats: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """建立连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_stats[client_id] = {
            "connected_at": time.time(),
            "frames_processed": 0,
            "total_processing_time": 0,
            "last_fps": 0,
            "fps_history": []
        }
        print(f"WebSocket客户端 {client_id} 已连接")
    
    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.connection_stats:
            del self.connection_stats[client_id]
        print(f"WebSocket客户端 {client_id} 已断开")
    
    async def send_message(self, client_id: str, message: dict):
        """发送消息"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except Exception as e:
                print(f"发送消息失败: {e}")
                self.disconnect(client_id)
    
    def update_stats(self, client_id: str, processing_time: float):
        """更新连接统计"""
        if client_id in self.connection_stats:
            stats = self.connection_stats[client_id]
            stats["frames_processed"] += 1
            stats["total_processing_time"] += processing_time
            
            # 计算FPS（基于最近10帧）
            current_time = time.time()
            stats["fps_history"].append(current_time)
            
            # 保持最近10个时间戳
            if len(stats["fps_history"]) > 10:
                stats["fps_history"] = stats["fps_history"][-10:]
            
            # 计算FPS
            if len(stats["fps_history"]) >= 2:
                time_span = stats["fps_history"][-1] - stats["fps_history"][0]
                if time_span > 0:
                    stats["last_fps"] = (len(stats["fps_history"]) - 1) / time_span
    
    def get_stats(self, client_id: str) -> Dict:
        """获取连接统计"""
        if client_id in self.connection_stats:
            stats = self.connection_stats[client_id].copy()
            stats["average_processing_time"] = (
                stats["total_processing_time"] / stats["frames_processed"] 
                if stats["frames_processed"] > 0 else 0
            )
            return stats
        return {}

manager = ConnectionManager()

@router.websocket("/ws/realtime/{client_id}")
async def realtime_detection_endpoint(
    websocket: WebSocket, 
    client_id: str,
    include_body: bool = Query(True),
    include_hands: bool = Query(True),
    target_fps: float = Query(15.0, ge=1.0, le=30.0)
):
    """
    实时检测WebSocket端点
    基于demo_camera.py的处理逻辑
    
    Args:
        client_id: 客户端唯一标识
        include_body: 是否检测身体
        include_hands: 是否检测手部
        target_fps: 目标FPS（1-30）
    """
    
    await manager.connect(websocket, client_id)
    
    # 获取检测服务
    detection_service = get_detection_service()
    
    # FPS控制
    frame_interval = 1.0 / target_fps
    last_frame_time = 0
    
    try:
        # 发送连接成功消息
        await manager.send_message(client_id, {
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "device": str(detection_service.device),
            "target_fps": target_fps,
            "timestamp": time.time()
        })
        
        while True:
            try:
                # 接收客户端数据，添加超时控制
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                current_time = time.time()
                
                # FPS控制
                time_since_last_frame = current_time - last_frame_time
                if time_since_last_frame < frame_interval:
                    await asyncio.sleep(frame_interval - time_since_last_frame)
                
                # 解析消息
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": "无效的JSON格式"
                    })
                    continue
                
                # 处理不同类型的消息
                if message.get("type") == "frame":
                    # 处理视频帧
                    await process_frame_message(
                        client_id, message, detection_service, 
                        include_body, include_hands
                    )
                    last_frame_time = time.time()
                    
                elif message.get("type") == "ping":
                    # 处理心跳ping消息
                    await manager.send_message(client_id, {
                        "type": "pong",
                        "timestamp": message.get("timestamp", time.time())
                    })
                    
                elif message.get("type") == "settings":
                    # 更新设置
                    include_body = message.get("include_body", include_body)
                    include_hands = message.get("include_hands", include_hands)
                    
                    await manager.send_message(client_id, {
                        "type": "settings_updated",
                        "include_body": include_body,
                        "include_hands": include_hands
                    })
                    
                elif message.get("type") == "stats_request":
                    # 发送统计信息
                    stats = manager.get_stats(client_id)
                    await manager.send_message(client_id, {
                        "type": "stats",
                        "data": stats
                    })
                
            except WebSocketDisconnect:
                break
            except asyncio.TimeoutError:
                # 超时，发送心跳检查连接
                try:
                    await manager.send_message(client_id, {
                        "type": "heartbeat",
                        "timestamp": time.time()
                    })
                except:
                    # 发送失败，连接已断开
                    break
            except Exception as e:
                print(f"处理WebSocket消息错误: {e}")
                traceback.print_exc()
                try:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": f"处理错误: {str(e)}"
                    })
                except:
                    # 发送失败，连接已断开
                    break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket连接错误: {e}")
        traceback.print_exc()
    finally:
        manager.disconnect(client_id)

async def process_frame_message(
    client_id: str, 
    message: dict, 
    detection_service, 
    include_body: bool, 
    include_hands: bool
):
    """处理视频帧消息"""
    
    frame_start_time = time.time()
    
    try:
        # 解码Base64图像
        base64_image = message.get("image", "")
        if not base64_image:
            await manager.send_message(client_id, {
                "type": "error",
                "message": "缺少图像数据"
            })
            return
        
        # 转换为OpenCV图像
        image = detection_service._base64_to_image(base64_image)
        if image is None:
            await manager.send_message(client_id, {
                "type": "error",
                "message": "图像解码失败"
            })
            return
        
        # 执行检测（类似demo_camera.py的process_frame逻辑）
        result = detection_service.detect_pose(
            image=image,
            include_body=include_body,
            include_hands=include_hands,
            draw_result=True
        )
        
        # 更新统计信息
        processing_time = time.time() - frame_start_time
        manager.update_stats(client_id, processing_time)
        
        # 获取当前统计
        stats = manager.get_stats(client_id)
        
        # 发送检测结果 - 优先发送关键点数据，减少传输量
        response = {
            "type": "detection_result",
            "success": result["success"],
            "device": result["device"],
            "processing_time": result["processing_time"],
            "frame_processing_time": processing_time,
            "detection_results": result["detection_results"],
            "performance": {
                "fps": round(stats.get("last_fps", 0), 2),
                "frames_processed": stats.get("frames_processed", 0),
                "average_processing_time": round(stats.get("average_processing_time", 0), 3)
            },
            "timestamp": time.time()
        }
        
        # 可选：根据客户端需求决定是否发送result_image
        # 默认不发送，减少网络传输量，提升性能
        if message.get("include_result_image", False):
            response["result_image"] = result.get("result_image")
        
        await manager.send_message(client_id, response)
        
    except Exception as e:
        print(f"处理帧错误: {e}")
        traceback.print_exc()
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"帧处理错误: {str(e)}"
        })

@router.get("/realtime/stats")
async def get_realtime_stats():
    """获取实时检测统计信息"""
    
    active_connections = len(manager.active_connections)
    total_stats = {
        "active_connections": active_connections,
        "connections": {}
    }
    
    for client_id, stats in manager.connection_stats.items():
        total_stats["connections"][client_id] = manager.get_stats(client_id)
    
    return total_stats

@router.post("/realtime/demo")
async def demo_realtime():
    """
    实时检测演示
    提供WebSocket连接的示例和测试说明
    """
    
    return {
        "message": "实时检测WebSocket演示",
        "websocket_url": "ws://localhost:8000/api/ws/realtime/{client_id}",
        "parameters": {
            "client_id": "客户端唯一标识",
            "include_body": "是否检测身体姿态（默认true）",
            "include_hands": "是否检测手部姿态（默认true）",
            "target_fps": "目标FPS（1-30，默认15）"
        },
        "message_format": {
            "发送帧": {
                "type": "frame",
                "image": "base64编码的图像数据"
            },
            "更新设置": {
                "type": "settings",
                "include_body": "bool",
                "include_hands": "bool"
            },
            "请求统计": {
                "type": "stats_request"
            }
        },
        "example_url": "ws://localhost:8000/api/ws/realtime/demo_client?include_body=true&include_hands=true&target_fps=15"
    }
