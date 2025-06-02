import cv2
import matplotlib.pyplot as plt
import copy
import numpy as np
import torch
import time

from src import model
from src import util
from src.body import Body
from src.hand import Hand

# 显示设备信息
print("="*50)
print("PyTorch OpenPose 实时摄像头演示")
print("="*50)
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA是否可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU设备: {torch.cuda.get_device_name(0)}")
    print(f"CUDA版本: {torch.version.cuda}")
else:
    print("将使用CPU进行推理")
print("="*50)

body_estimation = Body('model/body_pose_model.pth')
hand_estimation = Hand('model/hand_pose_model.pth')

cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

# 性能监控变量
frame_count = 0
fps_start_time = time.time()

print("开始实时检测...")
print("按 'q' 键退出")

while True:
    ret, oriImg = cap.read()
    if not ret:
        print("无法读取摄像头画面")
        break
    
    # 记录帧处理开始时间
    frame_start_time = time.time()
    
    candidate, subset = body_estimation(oriImg)
    canvas = copy.deepcopy(oriImg)
    canvas = util.draw_bodypose(canvas, candidate, subset)

    # detect hand
    hands_list = util.handDetect(candidate, subset, oriImg)

    all_hand_peaks = []
    for x, y, w, is_left in hands_list:
        peaks = hand_estimation(oriImg[y:y+w, x:x+w, :])
        peaks[:, 0] = np.where(peaks[:, 0]==0, peaks[:, 0], peaks[:, 0]+x)
        peaks[:, 1] = np.where(peaks[:, 1]==0, peaks[:, 1], peaks[:, 1]+y)
        all_hand_peaks.append(peaks)

    canvas = util.draw_handpose(canvas, all_hand_peaks)
    
    # 计算处理时间和FPS
    frame_time = time.time() - frame_start_time
    frame_count += 1
    
    # 每30帧显示一次FPS
    if frame_count % 30 == 0:
        elapsed_time = time.time() - fps_start_time
        fps = 30 / elapsed_time if elapsed_time > 0 else 0
        print(f"FPS: {fps:.2f}, 帧处理时间: {frame_time:.3f}秒")
        fps_start_time = time.time()
    
    # 在画面上显示性能信息
    device_text = "GPU" if torch.cuda.is_available() else "CPU"
    cv2.putText(canvas, f"Device: {device_text}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(canvas, f"Frame time: {frame_time:.3f}s", (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow('PyTorch OpenPose Demo', canvas)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

print("实时检测结束")

