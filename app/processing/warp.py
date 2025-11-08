import cv2
import numpy as np
from typing import Tuple, Dict, Any, List

class WarpingProcessor:
    #Khởi tạo
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.P_CFG = config.get('preprocessing', {})

    #Chuyển thành ảnh nhị phân để quét 4 marker
    def _preprocess_marker(self, img_gray: np.ndarray) -> np.ndarray:
        _, img_binary_marker = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV) 
        return img_binary_marker

    #Xử lý ảnh trước khi quét các marker đáp án
    def _preprocess_bubble(self, img_gray: np.ndarray) -> np.ndarray:
        threshold_value = self.P_CFG.get('threshold_value', 127)
        _, img_binary_bubble = cv2.threshold(img_gray, threshold_value, 255, cv2.THRESH_BINARY_INV)
        return img_binary_bubble

    def _find_and_order_markers(self, img_binary_marker: np.ndarray) -> List[Tuple[int, int, int, int]]:
        contours, _ = cv2.findContours(img_binary_marker, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        markers = []
        min_size = 0.5 * self.config['marker_scaling_ref'] * img_binary_marker.shape[1]
        min_density = 0.7 
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < min_size or h < min_size: continue
            aspect_ratio = w / h
            if not (0.8 <= aspect_ratio <= 1.2): continue 
            roi = img_binary_marker[y:y+h, x:x+w]
            density = np.sum(roi==255) / (w*h)
            if density >= min_density:
                markers.append((x, y, w, h))

        if len(markers) < 4:
            raise ValueError(f"Không tìm thấy đủ 4 marker góc. Chỉ tìm thấy {len(markers)}.")

        centers = np.array([[x + w//2, y + h//2] for x, y, w, h in markers])
        s = centers.sum(axis=1)
        diff = np.diff(centers, axis=1)

        tl_idx = np.argmin(s)
        br_idx = np.argmax(s)
        tr_idx = np.argmin(diff)
        bl_idx = np.argmax(diff)

        return [markers[tl_idx], markers[tr_idx], markers[br_idx], markers[bl_idx]]

    def process_warping(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:

        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        img_binary_marker = self._preprocess_marker(img_gray)
        img_binary_bubble = self._preprocess_bubble(img_gray)
        
        [tl_rect, tr_rect, br_rect, bl_rect] = self._find_and_order_markers(img_binary_marker)
        
        SRC_POINTS = np.float32([
            [tl_rect[0], tl_rect[1]], 
            [tr_rect[0], tr_rect[1]], 
            [br_rect[0], br_rect[1]], 
            [bl_rect[0], bl_rect[1]] 
        ])
        
        warp_w = self.config['warp_size']['width']
        warp_h = self.config['warp_size']['height']
        
        DST_POINTS = np.float32([
            [0, 0], 
            [warp_w, 0], 
            [warp_w, warp_h], 
            [0, warp_h]
        ])
        
        M = cv2.getPerspectiveTransform(SRC_POINTS, DST_POINTS)
        warp_size = (warp_w, warp_h)

        img_warped_bgr = cv2.warpPerspective(img_bgr, M, warp_size)
        img_warped_binary = cv2.warpPerspective(img_binary_bubble, M, warp_size)

        return img_warped_bgr, img_warped_binary