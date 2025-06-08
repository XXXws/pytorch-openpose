import cv2
import json
import numpy as np
import math
import time
import matplotlib.pyplot as plt
import matplotlib
import torch
import torch.nn.functional as F
from skimage.measure import label

from src.model import handpose_model
from src import util
from app.config import settings

class Hand(object):
    def __init__(self, model_path):
        # Benchmark CPU vs GPU and select faster device
        temp_model = handpose_model().eval()
        dummy = torch.zeros(1, 3, 368, 368)
        with torch.no_grad():
            start = time.time()
            temp_model(dummy)
            cpu_time = time.time() - start
        gpu_time = float('inf')
        if torch.cuda.is_available():
            temp_model = temp_model.to('cuda')
            with torch.no_grad():
                start = time.time()
                temp_model(dummy.to('cuda'))
                torch.cuda.synchronize()
                gpu_time = time.time() - start
        self.device = torch.device('cuda' if torch.cuda.is_available() and gpu_time < cpu_time else 'cpu')
        print(f"Using device for hand pose detection: {self.device}")

        self.model = handpose_model().to(self.device)
        if self.device.type == "cuda" and settings.enable_mixed_precision:
            self.model.half()

        model_dict = util.transfer(self.model, torch.load(model_path, map_location=self.device))
        
        self.model.load_state_dict(model_dict)
        self.model.eval()

        if settings.enable_torchscript:
            example = torch.zeros(1, 3, 368, 368, device=self.device)
            if self.device.type == "cuda" and settings.enable_mixed_precision:
                example = example.half()
            with torch.no_grad():
                traced = torch.jit.trace(self.model, example)
            self.model = torch.jit.optimize_for_inference(traced).to(self.device)
            if self.device.type == "cuda" and settings.enable_mixed_precision:
                self.model.half()
            self.model.eval()
        
        # GPU内存管理优化
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def __call__(self, oriImg):
        scale_search = [0.5, 1.0, 1.5, 2.0]
        # scale_search = [0.5]
        boxsize = 368
        stride = 8
        padValue = 128
        thre = 0.05
        multiplier = [x * boxsize / oriImg.shape[0] for x in scale_search]
        heatmap_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 22))
        # paf_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 38))

        for m in range(len(multiplier)):
            scale = multiplier[m]
            imageToTest = cv2.resize(oriImg, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            imageToTest_padded, pad = util.padRightDownCorner(imageToTest, stride, padValue)
            im = np.transpose(np.float32(imageToTest_padded[:, :, :, np.newaxis]), (3, 2, 0, 1)) / 256 - 0.5
            im = np.ascontiguousarray(im)

            data = torch.from_numpy(im).float()
            data = data.to(self.device)
            if self.device.type == "cuda" and settings.enable_mixed_precision:
                data = data.half()
            # data = data.permute([2, 0, 1]).unsqueeze(0).float()
            with torch.no_grad():
                if self.device.type == "cuda" and settings.enable_mixed_precision:
                    with torch.amp.autocast("cuda"):
                        output = self.model(data).float().cpu().numpy()
                else:
                    output = self.model(data).float().cpu().numpy()
                # output = self.model(data).numpy()q

            # extract outputs, resize, and remove padding
            heatmap = np.transpose(np.squeeze(output), (1, 2, 0))  # output 1 is heatmaps
            heatmap = cv2.resize(heatmap, (0, 0), fx=stride, fy=stride, interpolation=cv2.INTER_CUBIC)
            heatmap = heatmap[:imageToTest_padded.shape[0] - pad[2], :imageToTest_padded.shape[1] - pad[3], :]
            heatmap = cv2.resize(heatmap, (oriImg.shape[1], oriImg.shape[0]), interpolation=cv2.INTER_CUBIC)

            heatmap_avg += heatmap / len(multiplier)

            # 清理GPU缓存以释放内存
            if torch.cuda.is_available():
                del data
                torch.cuda.empty_cache()

        heatmap_t = torch.from_numpy(heatmap_avg.transpose(2, 0, 1)).to(self.device)
        smoothed = F.gaussian_blur(heatmap_t.unsqueeze(0), (7, 7), sigma=3)[0]
        all_peaks = []
        for part in range(21):
            part_map = smoothed[part]
            max_val = part_map.max()
            if max_val <= thre:
                all_peaks.append([0, 0])
                continue
            yx = torch.nonzero(part_map == max_val, as_tuple=False)[0]
            y, x = int(yx[0]), int(yx[1])
            all_peaks.append([x, y])
        return np.array(all_peaks)

if __name__ == "__main__":
    hand_estimation = Hand('../model/hand_pose_model.pth')

    # test_image = '../images/hand.jpg'
    test_image = '../images/hand.jpg'
    oriImg = cv2.imread(test_image)  # B,G,R order
    peaks = hand_estimation(oriImg)
    canvas = util.draw_handpose(oriImg, peaks, True)
    cv2.imshow('', canvas)
    cv2.waitKey(0)