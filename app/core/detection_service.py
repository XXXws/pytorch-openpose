#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenPose检测服务模块
基于已有的GPU优化Body和Hand类，提供Web API所需的检测服务
"""

import torch
import cv2
import numpy as np
import time
import io
import base64
import copy
from typing import Dict, List, Any, Optional
from PIL import Image

# 导入已有的GPU优化模块
from src.body import Body
from src.hand import Hand
from src import util

class OpenPoseDetectionService:
    """OpenPose检测服务类"""
    
    def __init__(self):
        """初始化检测服务"""
        print("Initializing OpenPose detection service...")
        
        # 设备检测
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # 加载模型
        try:
            # 确保使用绝对路径
            import os
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            body_model_path = os.path.join(current_dir, 'model', 'body_pose_model.pth')
            hand_model_path = os.path.join(current_dir, 'model', 'hand_pose_model.pth')
            
            print(f"Loading body model from: {body_model_path}")
            if not os.path.exists(body_model_path):
                raise FileNotFoundError(f"Body model file not found: {body_model_path}")
            
            self.body_estimation = Body(body_model_path)
            print("GPU optimized Body class imported successfully")
            
            print(f"Loading hand model from: {hand_model_path}")
            if not os.path.exists(hand_model_path):
                raise FileNotFoundError(f"Hand model file not found: {hand_model_path}")
            
            self.hand_estimation = Hand(hand_model_path)
            print("GPU optimized Hand class imported successfully")
            
            # 模型预热
            self._warmup_models()
            
        except Exception as e:
            print(f"Model loading failed: {e}")
            raise e
        
        print("OpenPose detection service initialization completed")
    
    def _warmup_models(self):
        """预热模型，避免首次推理延迟"""
        try:
            print("Starting model warmup...")
            
            # 创建测试图像
            test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # 预热身体检测模型
            candidate, subset = self.body_estimation(test_image)
            
            # 如果检测到手部区域，也预热手部模型
            hands_list = util.handDetect(candidate, subset, test_image)
            if hands_list:
                for x, y, w, is_left in hands_list[:1]:  # 只预热一个手部区域
                    if w > 20:  # 确保区域足够大
                        hand_roi = test_image[y:y+w, x:x+w, :]
                        if hand_roi.size > 0:
                            self.hand_estimation(hand_roi)
            
            print("Model warmup successful")
            
        except Exception as e:
            print(f"Model warmup failed: {e}")
    
    def detect_pose(
        self, 
        image: np.ndarray, 
        include_body: bool = True, 
        include_hands: bool = True,
        draw_result: bool = True
    ) -> Dict[str, Any]:
        """
        执行姿态检测
        
        Args:
            image: 输入图像 (BGR格式)
            include_body: 是否进行身体检测
            include_hands: 是否进行手部检测
            draw_result: 是否绘制结果图像
            
        Returns:
            检测结果字典
        """
        start_time = time.time()
        
        try:
            result = {
                "success": True,
                "device": str(self.device),
                "timestamp": time.time(),
                "processing_time": 0,
                "image_info": {
                    "height": image.shape[0],
                    "width": image.shape[1],
                    "channels": image.shape[2]
                },
                "detection_results": {}
            }
            
            # 复制原图用于绘制
            canvas = copy.deepcopy(image) if draw_result else None
            
            # 身体姿态检测
            candidate = None
            subset = None
            
            if include_body:
                body_start = time.time()
                candidate, subset = self.body_estimation(image)
                body_time = time.time() - body_start
                
                # 统计身体检测结果
                num_people = len(subset) if subset is not None else 0
                num_keypoints = len(candidate) if candidate is not None else 0
                
                result["detection_results"]["body"] = {
                    "detected": True,
                    "num_people": num_people,
                    "num_keypoints": num_keypoints,
                    "processing_time": round(body_time, 3),
                    "candidate": candidate.tolist() if candidate is not None else [],
                    "subset": subset.tolist() if subset is not None else []
                }
                
                # 绘制身体姿态
                if draw_result and canvas is not None:
                    canvas = util.draw_bodypose(canvas, candidate, subset)
                
                print(f"Body detection completed: {num_people} people, {num_keypoints} keypoints, time: {body_time:.3f}s")
            
            # 手部姿态检测
            if include_hands and candidate is not None and subset is not None:
                hand_start = time.time()
                
                # 检测手部区域
                hands_list = util.handDetect(candidate, subset, image)
                all_hand_peaks = []
                
                for x, y, w, is_left in hands_list:
                    try:
                        # 提取手部区域
                        hand_roi = image[y:y+w, x:x+w, :]
                        
                        # 手部关键点检测
                        peaks = self.hand_estimation(hand_roi)
                        
                        # 坐标转换回原图
                        peaks[:, 0] = np.where(peaks[:, 0] == 0, peaks[:, 0], peaks[:, 0] + x)
                        peaks[:, 1] = np.where(peaks[:, 1] == 0, peaks[:, 1], peaks[:, 1] + y)
                        
                        all_hand_peaks.append({
                            "peaks": peaks.tolist(),
                            "bbox": [int(x), int(y), int(w)],
                            "is_left": bool(is_left)
                        })
                        
                    except Exception as e:
                        print(f"Hand detection error: {e}")
                        continue
                
                hand_time = time.time() - hand_start
                
                result["detection_results"]["hands"] = {
                    "detected": True,
                    "num_hands": len(all_hand_peaks),
                    "processing_time": round(hand_time, 3),
                    "hands_data": all_hand_peaks
                }
                
                # 绘制手部姿态
                if draw_result and canvas is not None:
                    # 提取peaks用于绘制
                    peaks_for_draw = [np.array(hand["peaks"]) for hand in all_hand_peaks]
                    canvas = util.draw_handpose(canvas, peaks_for_draw)
                
                print(f"Hand detection completed: {len(all_hand_peaks)} hands, time: {hand_time:.3f}s")
            
            # 处理结果图像（可选，用于备用显示）
            if draw_result and canvas is not None:
                # 转换为Base64编码
                result["result_image"] = self._image_to_base64(canvas)
            
            # 添加关键点数据的简化版本，用于前端快速渲染
            result["keypoints_summary"] = {
                "body_detected": include_body and candidate is not None and len(candidate) > 0,
                "hands_detected": include_hands and "hands" in result["detection_results"] and result["detection_results"]["hands"]["num_hands"] > 0,
                "total_people": len(subset) if subset is not None else 0,
                "total_hands": result["detection_results"].get("hands", {}).get("num_hands", 0)
            }
            
            # 计算总处理时间
            total_time = time.time() - start_time
            result["processing_time"] = round(total_time, 3)
            
            print(f"Total detection time: {total_time:.3f}s")
            
            return result
            
        except Exception as e:
            print(f"Error occurred during detection: {e}")
            return {
                "success": False,
                "error": str(e),
                "device": str(self.device),
                "timestamp": time.time(),
                "processing_time": round(time.time() - start_time, 3)
            }
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """将OpenCV图像转换为Base64编码字符串"""
        try:
            # 使用cv2编码，避免颜色空间转换
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            # 编码为Base64
            img_str = base64.b64encode(buffer).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
        except Exception as e:
            print(f"Image Base64 encoding failed: {e}")
            return ""
    
    def _base64_to_image(self, base64_str: str) -> Optional[np.ndarray]:
        """将Base64编码字符串转换为OpenCV图像"""
        try:
            # 移除data URL前缀
            if base64_str.startswith('data:image'):
                base64_str = base64_str.split(',')[1]
            
            # 解码Base64
            img_data = base64.b64decode(base64_str)
            
            # 直接使用cv2解码，保持一致性
            nparr = np.frombuffer(img_data, np.uint8)
            image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image_bgr is None:
                # 如果cv2解码失败，回退到PIL方式
                pil_image = Image.open(io.BytesIO(img_data))
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                image_rgb = np.array(pil_image)
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            
            return image_bgr
            
        except Exception as e:
            print(f"Base64 image decoding failed: {e}")
            return None
    
    def get_device_info(self) -> Dict[str, Any]:
        """获取当前设备信息"""
        info = {
            "device": str(self.device),
            "device_type": "GPU" if torch.cuda.is_available() else "CPU",
            "pytorch_version": torch.__version__
        }
        
        if torch.cuda.is_available():
            info.update({
                "cuda_version": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_memory": {
                    "allocated_gb": round(torch.cuda.memory_allocated(0) / 1024**3, 3),
                    "cached_gb": round(torch.cuda.memory_reserved(0) / 1024**3, 3)
                }
            })
        
        return info

# 全局检测服务实例
_detection_service: Optional[OpenPoseDetectionService] = None

def get_detection_service() -> OpenPoseDetectionService:
    """获取检测服务单例"""
    global _detection_service
    if _detection_service is None:
        _detection_service = OpenPoseDetectionService()
    return _detection_service 