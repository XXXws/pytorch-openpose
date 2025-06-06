#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Core video processing utilities."""

import copy
from typing import Optional

import cv2
import numpy as np

from src.body import Body
from src.hand import Hand
from src import util


class VideoProcessingService:
    """Service providing frame level pose detection."""

    def __init__(self) -> None:
        self.body_estimation = Body('model/body_pose_model.pth')
        self.hand_estimation = Hand('model/hand_pose_model.pth')

    def process_frame(self, frame: np.ndarray, include_body: bool = True, include_hands: bool = True) -> np.ndarray:
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
                except Exception:
                    continue
            canvas = util.draw_handpose(canvas, all_hand_peaks)
        return canvas


_video_service: Optional[VideoProcessingService] = None
_video_service_lock = None


def get_video_service() -> VideoProcessingService:
    global _video_service, _video_service_lock
    if _video_service is None:
        import threading
        if _video_service_lock is None:
            _video_service_lock = threading.Lock()
        with _video_service_lock:
            if _video_service is None:
                _video_service = VideoProcessingService()
    return _video_service
