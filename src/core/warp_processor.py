import cv2
import numpy as np
from typing import Tuple, Dict, Any, List, Optional
from src.utils import app_logger

class WarpingProcessor:
    """
    Chịu trách nhiệm xử lý hình học của ảnh:
    1. Tiền xử lý (Thresholding).
    2. Tìm 4 điểm định vị (Markers) ở góc.
    3. Biến đổi phối cảnh (Perspective Transform) để làm phẳng ảnh.
    """

    # Các hằng số mặc định (Fallback nếu config thiếu)
    DEFAULT_THRESHOLD = 127
    MIN_MARKER_DENSITY = 0.7
    MARKER_ASPECT_RATIO_RANGE = (0.8, 1.2)

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.preprocessing_cfg = config.get('preprocessing', {})
        app_logger.debug("WarpingProcessor initialized with config.")

    def _preprocess_marker(self, img_gray: np.ndarray) -> np.ndarray:
        """Chuyển ảnh xám thành nhị phân để tìm marker (Inverse Binary)."""
        # Sử dụng ngưỡng cố định 127 cho marker (thường là chuẩn)
        _, img_binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)
        return img_binary

    def _preprocess_bubble(self, img_gray: np.ndarray) -> np.ndarray:
        """Chuyển ảnh xám thành nhị phân để quét đáp án."""
        thresh_val = self.preprocessing_cfg.get('threshold_value', self.DEFAULT_THRESHOLD)
        _, img_binary = cv2.threshold(img_gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
        return img_binary

    def _find_and_order_markers(self, img_binary_marker: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Tìm 4 marker và sắp xếp theo thứ tự: TL, TR, BR, BL."""
        contours, _ = cv2.findContours(img_binary_marker, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        markers = []
        img_h, img_w = img_binary_marker.shape
        
        # Lấy tham số scaling từ config hoặc dùng mặc định
        marker_scaling_ref = self.config.get('marker_scaling_ref', 0.05) 
        min_size = 0.5 * marker_scaling_ref * img_w
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # 1. Lọc theo kích thước
            if w < min_size or h < min_size: 
                continue
            
            # 2. Lọc theo tỷ lệ khung hình (gần vuông)
            aspect_ratio = w / h
            if not (self.MARKER_ASPECT_RATIO_RANGE[0] <= aspect_ratio <= self.MARKER_ASPECT_RATIO_RANGE[1]): 
                continue 
            
            # 3. Lọc theo độ đặc (Density) - Marker phải là hình đặc
            roi = img_binary_marker[y:y+h, x:x+w]
            density = np.sum(roi == 255) / (w * h)
            if density >= self.MIN_MARKER_DENSITY:
                markers.append((x, y, w, h))

        # Kiểm tra số lượng marker tìm thấy
        if len(markers) < 4:
            app_logger.error(f"Warping Failed: Found {len(markers)} markers, expected 4.")
            raise ValueError(f"Không tìm thấy đủ 4 điểm định vị. Chỉ tìm thấy {len(markers)} điểm.")

        # Sắp xếp marker: Top-Left, Top-Right, Bottom-Right, Bottom-Left
        centers = np.array([[x + w//2, y + h//2] for x, y, w, h in markers])
        
        # Logic sắp xếp dựa trên tổng và hiệu tọa độ
        s = centers.sum(axis=1)
        diff = np.diff(centers, axis=1)

        tl_idx = np.argmin(s)
        br_idx = np.argmax(s)
        tr_idx = np.argmin(diff)
        bl_idx = np.argmax(diff)

        ordered_markers = [markers[tl_idx], markers[tr_idx], markers[br_idx], markers[bl_idx]]
        app_logger.debug(f"Markers ordered successfully. Centers: {centers[tl_idx]}, {centers[tr_idx]}, ...")
        
        return ordered_markers

    def process_warping(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Quy trình chính: Input ảnh BGR -> Output ảnh đã Warp (BGR & Binary).
        """
        try:
            h, w = img_bgr.shape[:2]
            app_logger.info(f"Processing image for warping. Input size: {w}x{h}")

            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            
            # Preprocess
            img_binary_marker = self._preprocess_marker(img_gray)
            img_binary_bubble = self._preprocess_bubble(img_gray)
            
            # Tìm 4 điểm
            [tl, tr, br, bl] = self._find_and_order_markers(img_binary_marker)
            
            # Điểm nguồn (Source points)
            src_pts = np.float32([
                [tl[0], tl[1]], 
                [tr[0], tr[1]], 
                [br[0], br[1]], 
                [bl[0], bl[1]] 
            ])
            
            # Điểm đích (Destination points) - Lấy từ Config
            warp_w = self.config['warp_size']['width']
            warp_h = self.config['warp_size']['height']
            
            dst_pts = np.float32([
                [0, 0], 
                [warp_w, 0], 
                [warp_w, warp_h], 
                [0, warp_h]
            ])
            
            # Tạo ma trận biến đổi và áp dụng
            matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
            warp_size = (warp_w, warp_h)

            img_warped_bgr = cv2.warpPerspective(img_bgr, matrix, warp_size)
            img_warped_binary = cv2.warpPerspective(img_binary_bubble, matrix, warp_size)
            img_warped_marker = cv2.warpPerspective(img_binary_marker, matrix, warp_size)

            app_logger.info("Warping completed successfully.")
            return img_warped_bgr, img_warped_binary, img_warped_marker

        except Exception as e:
            app_logger.error(f"Error during warping process: {e}")
            raise