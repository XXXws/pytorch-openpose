import cv2
import numpy as np
import math
import time
import matplotlib.pyplot as plt
import matplotlib
import torch
import torch.nn.functional as F

from src import util
from src.model import bodypose_model
from app.config import settings

class Body(object):
    def __init__(self, model_path):
        # Benchmark CPU vs GPU to select the faster device
        temp_model = bodypose_model().eval()
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
        print(f"Using device for body pose detection: {self.device}")

        # Initialize model on the selected device
        self.model = bodypose_model().to(self.device)
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
        # scale_search = [0.5, 1.0, 1.5, 2.0]
        scale_search = [0.5]
        boxsize = 368
        stride = 8
        padValue = 128
        thre1 = 0.1
        thre2 = 0.05
        multiplier = [x * boxsize / oriImg.shape[0] for x in scale_search]
        heatmap_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 19))
        paf_avg = np.zeros((oriImg.shape[0], oriImg.shape[1], 38))

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
                        Mconv7_stage6_L1, Mconv7_stage6_L2 = self.model(data)
                else:
                    Mconv7_stage6_L1, Mconv7_stage6_L2 = self.model(data)
            Mconv7_stage6_L1 = Mconv7_stage6_L1.float().cpu().numpy()
            Mconv7_stage6_L2 = Mconv7_stage6_L2.float().cpu().numpy()
            
            # 清理GPU缓存以释放内存
            if torch.cuda.is_available():
                del data
                torch.cuda.empty_cache()

            # extract outputs, resize, and remove padding
            # heatmap = np.transpose(np.squeeze(net.blobs[output_blobs.keys()[1]].data), (1, 2, 0))  # output 1 is heatmaps
            heatmap = np.transpose(np.squeeze(Mconv7_stage6_L2), (1, 2, 0))  # output 1 is heatmaps
            heatmap = cv2.resize(heatmap, (0, 0), fx=stride, fy=stride, interpolation=cv2.INTER_CUBIC)
            heatmap = heatmap[:imageToTest_padded.shape[0] - pad[2], :imageToTest_padded.shape[1] - pad[3], :]
            heatmap = cv2.resize(heatmap, (oriImg.shape[1], oriImg.shape[0]), interpolation=cv2.INTER_CUBIC)

            # paf = np.transpose(np.squeeze(net.blobs[output_blobs.keys()[0]].data), (1, 2, 0))  # output 0 is PAFs
            paf = np.transpose(np.squeeze(Mconv7_stage6_L1), (1, 2, 0))  # output 0 is PAFs
            paf = cv2.resize(paf, (0, 0), fx=stride, fy=stride, interpolation=cv2.INTER_CUBIC)
            paf = paf[:imageToTest_padded.shape[0] - pad[2], :imageToTest_padded.shape[1] - pad[3], :]
            paf = cv2.resize(paf, (oriImg.shape[1], oriImg.shape[0]), interpolation=cv2.INTER_CUBIC)

            heatmap_avg += heatmap / len(multiplier)
            paf_avg += paf / len(multiplier)

        all_peaks = []
        peak_counter = 0

        heatmap_t = torch.from_numpy(heatmap_avg.transpose(2, 0, 1)).to(self.device)
        smoothed = F.gaussian_blur(heatmap_t.unsqueeze(0), (7, 7), sigma=3)[0]
        max_map = F.max_pool2d(smoothed.unsqueeze(0), 3, stride=1, padding=1)[0]
        peaks_binary = (smoothed == max_map) & (smoothed > thre1)

        for part in range(18):
            coords = torch.nonzero(peaks_binary[part], as_tuple=False)
            scores = heatmap_t[part, coords[:, 0], coords[:, 1]] if coords.numel() > 0 else torch.tensor([])
            part_peaks = []
            for idx in range(coords.shape[0]):
                y, x = coords[idx]
                part_peaks.append((int(x), int(y), float(scores[idx]), peak_counter + idx))
            all_peaks.append(part_peaks)
            peak_counter += coords.shape[0]

        # find connection in the specified sequence, center 29 is in the position 15
        limbSeq = [[2, 3], [2, 6], [3, 4], [4, 5], [6, 7], [7, 8], [2, 9], [9, 10], \
                   [10, 11], [2, 12], [12, 13], [13, 14], [2, 1], [1, 15], [15, 17], \
                   [1, 16], [16, 18], [3, 17], [6, 18]]
        # the middle joints heatmap correpondence
        mapIdx = [[31, 32], [39, 40], [33, 34], [35, 36], [41, 42], [43, 44], [19, 20], [21, 22], \
                  [23, 24], [25, 26], [27, 28], [29, 30], [47, 48], [49, 50], [53, 54], [51, 52], \
                  [55, 56], [37, 38], [45, 46]]

        connection_all = []
        special_k = []
        mid_num = 10

        for k in range(len(mapIdx)):
            score_mid = paf_avg[:, :, [x - 19 for x in mapIdx[k]]]
            candA = all_peaks[limbSeq[k][0] - 1]
            candB = all_peaks[limbSeq[k][1] - 1]
            nA = len(candA)
            nB = len(candB)
            indexA, indexB = limbSeq[k]
            if (nA != 0 and nB != 0):
                connection_candidate = []
                for i in range(nA):
                    for j in range(nB):
                        vec = np.subtract(candB[j][:2], candA[i][:2]).astype(np.float32)
                        norm = math.hypot(vec[0], vec[1])
                        norm = max(0.001, norm)
                        vec_unit = vec / norm

                        xs = torch.linspace(candA[i][0], candB[j][0], mid_num, device=self.device)
                        ys = torch.linspace(candA[i][1], candB[j][1], mid_num, device=self.device)
                        xs_int = xs.round().long()
                        ys_int = ys.round().long()
                        paf_x = torch.tensor(score_mid[:, :, 0], device=self.device)[ys_int, xs_int]
                        paf_y = torch.tensor(score_mid[:, :, 1], device=self.device)[ys_int, xs_int]
                        score_midpts = paf_x * vec_unit[0] + paf_y * vec_unit[1]
                        score_with_dist_prior = score_midpts.mean().item() + min(0.5 * oriImg.shape[0] / norm - 1, 0)
                        criterion1 = (score_midpts > thre2).sum().item() > 0.8 * mid_num
                        criterion2 = score_with_dist_prior > 0
                        if criterion1 and criterion2:
                            connection_candidate.append(
                                [i, j, score_with_dist_prior, score_with_dist_prior + candA[i][2] + candB[j][2]])

                connection_candidate = sorted(connection_candidate, key=lambda x: x[2], reverse=True)
                connection = np.zeros((0, 5))
                for c in range(len(connection_candidate)):
                    i, j, s = connection_candidate[c][0:3]
                    if (i not in connection[:, 3] and j not in connection[:, 4]):
                        connection = np.vstack([connection, [candA[i][3], candB[j][3], s, i, j]])
                        if (len(connection) >= min(nA, nB)):
                            break

                connection_all.append(connection)
            else:
                special_k.append(k)
                connection_all.append([])

        # last number in each row is the total parts number of that person
        # the second last number in each row is the score of the overall configuration
        subset = -1 * np.ones((0, 20))
        candidate = np.array([item for sublist in all_peaks for item in sublist])

        for k in range(len(mapIdx)):
            if k not in special_k:
                partAs = connection_all[k][:, 0]
                partBs = connection_all[k][:, 1]
                indexA, indexB = np.array(limbSeq[k]) - 1

                for i in range(len(connection_all[k])):  # = 1:size(temp,1)
                    found = 0
                    subset_idx = [-1, -1]
                    for j in range(len(subset)):  # 1:size(subset,1):
                        if subset[j][indexA] == partAs[i] or subset[j][indexB] == partBs[i]:
                            subset_idx[found] = j
                            found += 1

                    if found == 1:
                        j = subset_idx[0]
                        if subset[j][indexB] != partBs[i]:
                            subset[j][indexB] = partBs[i]
                            subset[j][-1] += 1
                            subset[j][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]
                    elif found == 2:  # if found 2 and disjoint, merge them
                        j1, j2 = subset_idx
                        membership = ((subset[j1] >= 0).astype(int) + (subset[j2] >= 0).astype(int))[:-2]
                        if len(np.nonzero(membership == 2)[0]) == 0:  # merge
                            subset[j1][:-2] += (subset[j2][:-2] + 1)
                            subset[j1][-2:] += subset[j2][-2:]
                            subset[j1][-2] += connection_all[k][i][2]
                            subset = np.delete(subset, j2, 0)
                        else:  # as like found == 1
                            subset[j1][indexB] = partBs[i]
                            subset[j1][-1] += 1
                            subset[j1][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]

                    # if find no partA in the subset, create a new subset
                    elif not found and k < 17:
                        row = -1 * np.ones(20)
                        row[indexA] = partAs[i]
                        row[indexB] = partBs[i]
                        row[-1] = 2
                        row[-2] = sum(candidate[connection_all[k][i, :2].astype(int), 2]) + connection_all[k][i][2]
                        subset = np.vstack([subset, row])
        # delete some rows of subset which has few parts occur
        deleteIdx = []
        for i in range(len(subset)):
            if subset[i][-1] < 4 or subset[i][-2] / subset[i][-1] < 0.4:
                deleteIdx.append(i)
        subset = np.delete(subset, deleteIdx, axis=0)

        # subset: n*20 array, 0-17 is the index in candidate, 18 is the total score, 19 is the total parts
        # candidate: x, y, score, id
        return candidate, subset

if __name__ == "__main__":
    body_estimation = Body('../model/body_pose_model.pth')

    test_image = '../images/ski.jpg'
    oriImg = cv2.imread(test_image)  # B,G,R order
    candidate, subset = body_estimation(oriImg)
    canvas = util.draw_bodypose(oriImg, candidate, subset)
    plt.imshow(canvas[:, :, [2, 1, 0]])
    plt.show()
