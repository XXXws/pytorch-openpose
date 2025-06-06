#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姿态检测API路由
提供图像检测、文件上传、Base64编码等功能
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import cv2
import numpy as np
import os
import uuid
import time
from datetime import datetime
from typing import Optional, Dict, Any
import traceback
import logging

# 导入检测服务
from app.core.detection_service import get_detection_service

router = APIRouter()
logger = logging.getLogger(__name__)

class ImageDetectionRequest(BaseModel):
    """图像检测请求模型"""
    image_base64: str
    include_body: bool = True
    include_hands: bool = True
    draw_result: bool = True

class ImageDetectionResponse(BaseModel):
    """图像检测响应模型"""
    success: bool
    message: str
    device: str
    processing_time: float
    detection_results: Dict[str, Any]
    result_image: Optional[str] = None
    timestamp: str

@router.post("/detect/image", response_model=ImageDetectionResponse)
async def detect_image_base64(request: ImageDetectionRequest):
    """
    Base64图像检测接口
    接收Base64编码的图像，返回检测结果
    """
    try:
        logger.info(
            f"Received Base64 image detection request: body={request.include_body}, hands={request.include_hands}"
        )

        # 获取检测服务
        logger.debug("Getting detection service...")
        try:
            detection_service = get_detection_service()
            logger.debug("Detection service obtained successfully")
        except Exception as e:
            logger.exception(f"Failed to get detection service: {e}")
            raise HTTPException(status_code=500, detail=f"Detection service initialization failed: {str(e)}")
        
        # 解码Base64图像
        image = detection_service._base64_to_image(request.image_base64)
        if image is None:
            raise HTTPException(status_code=400, detail="Base64图像解码失败")
        
        # 执行检测
        result = detection_service.detect_pose(
            image=image,
            include_body=request.include_body,
            include_hands=request.include_hands,
            draw_result=request.draw_result
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"检测失败: {result.get('error', '未知错误')}")
        
        return ImageDetectionResponse(
            success=True,
            message="检测完成",
            device=result["device"],
            processing_time=result["processing_time"],
            detection_results=result["detection_results"],
            result_image=result.get("result_image"),
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Base64检测接口错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.post("/detect/upload")
async def detect_uploaded_image(
    file: UploadFile = File(...),
    include_body: bool = Form(True),
    include_hands: bool = Form(True),
    draw_result: bool = Form(True)
):
    """
    文件上传检测接口
    接收上传的图像文件，返回检测结果
    """
    try:
        logger.info(f"Received file upload detection request: {file.filename}")
        
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="请上传图像文件")
        
        # 读取文件内容
        contents = await file.read()
        
        # 转换为OpenCV图像
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="图像文件解码失败")
        
        # 保存上传的文件（可选）
        upload_filename = f"upload_{uuid.uuid4().hex[:8]}_{int(time.time())}.jpg"
        from app.config import settings
        upload_path = os.path.join(settings.upload_dir, upload_filename)
        cv2.imwrite(upload_path, image)
        
        # 获取检测服务并执行检测
        detection_service = get_detection_service()
        result = detection_service.detect_pose(
            image=image,
            include_body=include_body,
            include_hands=include_hands,
            draw_result=draw_result
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"检测失败: {result.get('error', '未知错误')}")
        
        # 保存结果图像（如果有）
        result_image_path = None
        if draw_result and "result_image" in result:
            result_filename = f"result_{uuid.uuid4().hex[:8]}_{int(time.time())}.jpg"
            result_path = os.path.join("results", result_filename)
            
            # 从Base64保存图像文件
            import base64
            import io
            from PIL import Image as PILImage
            
            base64_str = result["result_image"].split(',')[1] if ',' in result["result_image"] else result["result_image"]
            img_data = base64.b64decode(base64_str)
            pil_image = PILImage.open(io.BytesIO(img_data))
            pil_image.save(result_path, format='JPEG', quality=90)
            
            result_image_path = f"/results/{result_filename}"
        
        response_data = {
            "success": True,
            "message": "检测完成",
            "device": result["device"],
            "processing_time": result["processing_time"],
            "detection_results": result["detection_results"],
            "files": {
                "upload_path": f"/uploads/{upload_filename}",
                "result_path": result_image_path
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 如果请求Base64结果，也包含在响应中
        if draw_result and "result_image" in result:
            response_data["result_image"] = result["result_image"]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"File upload detection API error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/detect/demo")
async def demo_detection():
    """
    演示检测接口
    使用默认测试图像进行检测，复用demo.py的逻辑
    """
    try:
        print("执行演示检测...")
        
        # 查找测试图像
        test_images = []
        if os.path.exists("images"):
            for filename in os.listdir("images"):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    test_images.append(os.path.join("images", filename))
        
        if not test_images:
            raise HTTPException(status_code=404, detail="未找到测试图像，请在images/目录放置图像文件")
        
        # 使用第一张图像
        test_image_path = test_images[0]
        print(f"使用测试图像: {test_image_path}")
        
        # 读取图像
        image = cv2.imread(test_image_path)
        if image is None:
            raise HTTPException(status_code=400, detail=f"无法读取图像文件: {test_image_path}")
        
        # 获取检测服务并执行检测
        detection_service = get_detection_service()
        result = detection_service.detect_pose(
            image=image,
            include_body=True,
            include_hands=True,
            draw_result=True
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"检测失败: {result.get('error', '未知错误')}")
        
        # 保存演示结果
        demo_filename = f"demo_result_{int(time.time())}.jpg"
        demo_path = os.path.join("results", demo_filename)
        
        if "result_image" in result:
            # 从Base64保存图像文件
            import base64
            import io
            from PIL import Image as PILImage
            
            base64_str = result["result_image"].split(',')[1] if ',' in result["result_image"] else result["result_image"]
            img_data = base64.b64decode(base64_str)
            pil_image = PILImage.open(io.BytesIO(img_data))
            pil_image.save(demo_path, format='JPEG', quality=90)
        
        return {
            "success": True,
            "message": "演示检测完成",
            "device": result["device"],
            "processing_time": result["processing_time"],
            "detection_results": result["detection_results"],
            "result_image": result.get("result_image"),
            "files": {
                "source_image": test_image_path,
                "result_path": f"/results/{demo_filename}"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"演示检测接口错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/detect/status")
async def detection_status():
    """
    获取检测服务状态
    """
    try:
        detection_service = get_detection_service()
        device_info = detection_service.get_device_info()
        
        return {
            "status": "ready",
            "device_info": device_info,
            "timestamp": datetime.now().isoformat(),
            "service": "OpenPose Detection Service"
        }
        
    except Exception as e:
        print(f"Status query error: {e}")
        raise HTTPException(status_code=500, detail=f"Status query failed: {str(e)}")

@router.get("/detect/diagnose")
async def diagnose_detection_service():
    """
    诊断检测服务初始化状态
    """
    diagnosis = {
        "timestamp": datetime.now().isoformat(),
        "steps": []
    }
    
    try:
        # 步骤1：检查模型文件
        diagnosis["steps"].append({"step": "checking_model_files", "status": "starting"})
        
        import os
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        body_model_path = os.path.join(current_dir, 'model', 'body_pose_model.pth')
        hand_model_path = os.path.join(current_dir, 'model', 'hand_pose_model.pth')
        
        body_exists = os.path.exists(body_model_path)
        hand_exists = os.path.exists(hand_model_path)
        
        diagnosis["steps"].append({
            "step": "checking_model_files", 
            "status": "completed",
            "details": {
                "body_model_path": body_model_path,
                "body_model_exists": body_exists,
                "hand_model_path": hand_model_path,
                "hand_model_exists": hand_exists
            }
        })
        
        if not body_exists or not hand_exists:
            diagnosis["overall_status"] = "failed"
            diagnosis["error"] = "Model files not found"
            return diagnosis
        
        # 步骤2：检查依赖导入
        diagnosis["steps"].append({"step": "checking_imports", "status": "starting"})
        
        try:
            from src.body import Body
            from src.hand import Hand
            diagnosis["steps"].append({"step": "checking_imports", "status": "completed"})
        except Exception as e:
            diagnosis["steps"].append({
                "step": "checking_imports", 
                "status": "failed",
                "error": str(e)
            })
            diagnosis["overall_status"] = "failed"
            return diagnosis
        
        # 步骤3：尝试初始化检测服务
        diagnosis["steps"].append({"step": "initializing_service", "status": "starting"})
        
        try:
            detection_service = get_detection_service()
            device_info = detection_service.get_device_info()
            diagnosis["steps"].append({
                "step": "initializing_service", 
                "status": "completed",
                "device_info": device_info
            })
        except Exception as e:
            diagnosis["steps"].append({
                "step": "initializing_service", 
                "status": "failed",
                "error": str(e)
            })
            diagnosis["overall_status"] = "failed"
            return diagnosis
        
        diagnosis["overall_status"] = "success"
        return diagnosis
        
    except Exception as e:
        diagnosis["overall_status"] = "error"
        diagnosis["error"] = str(e)
        print(f"Diagnosis error: {e}")
        traceback.print_exc()
        return diagnosis

@router.post("/detect/batch")
async def batch_detection(
    files: list[UploadFile] = File(...),
    include_body: bool = Form(True),
    include_hands: bool = Form(True),
    draw_result: bool = Form(True)
):
    """
    批量检测接口
    接收多个图像文件，返回批量检测结果
    """
    try:
        print(f"收到批量检测请求: {len(files)}个文件")
        
        if len(files) > 10:  # 限制批量数量
            raise HTTPException(status_code=400, detail="批量检测最多支持10个文件")
        
        detection_service = get_detection_service()
        results = []
        
        for i, file in enumerate(files):
            try:
                print(f"处理文件 {i+1}/{len(files)}: {file.filename}")
                
                # 验证文件类型
                if not file.content_type or not file.content_type.startswith('image/'):
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "非图像文件"
                    })
                    continue
                
                # 读取文件内容
                contents = await file.read()
                nparr = np.frombuffer(contents, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": "图像解码失败"
                    })
                    continue
                
                # 执行检测
                result = detection_service.detect_pose(
                    image=image,
                    include_body=include_body,
                    include_hands=include_hands,
                    draw_result=draw_result
                )
                
                # 添加文件名信息
                result["filename"] = file.filename
                results.append(result)
                
            except Exception as e:
                print(f"处理文件 {file.filename} 时出错: {e}")
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        # 统计结果
        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful
        
        return {
            "success": True,
            "message": f"批量检测完成: {successful}成功, {failed}失败",
            "total_files": len(files),
            "successful_count": successful,
            "failed_count": failed,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"批量检测接口错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 