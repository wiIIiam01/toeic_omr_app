import cv2
import numpy as np
import re
from typing import Tuple, Dict, Any, List
from src.utils import app_logger

class WarpingProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.prep_cfg = config.get('preprocessing', {})
        self.warp_top = config.get('warp_top_size', {'width': 1320, 'height': 869})
        self.warp_bot = config.get('warp_bottom_size', {'width': 1214, 'height': 854})
        
        self.scale_ref = self.prep_cfg.get('marker_scaling_ref', 0.0225)
        self.aspect_range = self.prep_cfg.get('marker_aspect_ratio_range', [0.8, 1.2])
        self.min_density = self.prep_cfg.get('min_marker_density', 0.7)

    def _preprocess_marker(self, img_gray: np.ndarray) -> np.ndarray:
        _, img_binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)
        return img_binary

    def _preprocess_bubble(self, img_gray: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img_gray = clahe.apply(img_gray)
        _, img_binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return img_binary

    def _ensure_portrait_orientation(self, img_bgr: np.ndarray) -> np.ndarray:
        h, w = img_bgr.shape[:2]
        if w > h:
            app_logger.debug("Image is landscape. Rotating 90 degrees.")
            return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
        return img_bgr

    def _find_6_markers(self, img_binary_marker: np.ndarray) -> List[Dict[str, int]]:
        img_h, img_w = img_binary_marker.shape
        min_size = self.scale_ref * img_w
        
        contours, _ = cv2.findContours(img_binary_marker, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_markers = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w >= min_size and h >= min_size:
                aspect_ratio = w / h
                if self.aspect_range[0] <= aspect_ratio <= self.aspect_range[1]:
                    roi = img_binary_marker[y:y+h, x:x+w]
                    density = np.sum(roi == 255) / (w * h)
                    if density >= self.min_density:
                        valid_markers.append({'cx': x + w//2, 'cy': y + h//2, 'x': x, 'y': y, 'w': w, 'h': h})

        if len(valid_markers) != 6:
            raise ValueError(f"Tìm thấy {len(valid_markers)} marker. Yêu cầu chính xác 6 điểm neo.")

        valid_markers.sort(key=lambda m: m['cy'])
        top_pair = sorted(valid_markers[0:2], key=lambda m: m['cx'])
        mid_pair = sorted(valid_markers[2:4], key=lambda m: m['cx'])
        bot_pair = sorted(valid_markers[4:6], key=lambda m: m['cx'])

        return [top_pair[0], top_pair[1], mid_pair[0], mid_pair[1], bot_pair[0], bot_pair[1]]

    def _check_upside_down_and_rotate(self, img_bgr: np.ndarray, markers: List[Dict], img_bin: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
        TL, TR, ML, MR, BL, BR = markers
        
        def count_pixels_polygon(left_m, right_m):
            pt1 = [left_m['x'] + left_m['w'], left_m['y']]
            pt2 = [left_m['x'] + left_m['w'], left_m['y'] + left_m['h']]
            pt3 = [right_m['x'], right_m['y'] + right_m['h']]
            pt4 = [right_m['x'], right_m['y']]
            pts = np.array([pt1, pt2, pt3, pt4], np.int32).reshape((-1, 1, 2))
            
            mask = np.zeros_like(img_bin)
            cv2.fillPoly(mask, [pts], 255)
            return cv2.countNonZero(cv2.bitwise_and(img_bin, mask))

        if count_pixels_polygon(BL, BR) > count_pixels_polygon(TL, TR):
            app_logger.debug("Image is upside down. Rotating 180 degrees.")
            img_rotated = cv2.rotate(img_bgr, cv2.ROTATE_180)
            h_img, w_img = img_bgr.shape[:2]
            
            rotated_markers = [{'cx': w_img - m['cx'], 'cy': h_img - m['cy'], 'x': w_img - (m['x'] + m['w']), 'y': h_img - (m['y'] + m['h']), 'w': m['w'], 'h': m['h']} for m in reversed(markers)]
            
            final_markers = sorted(rotated_markers[0:2], key=lambda m: m['cx']) + sorted(rotated_markers[2:4], key=lambda m: m['cx']) + sorted(rotated_markers[4:6], key=lambda m: m['cx'])
            return img_rotated, final_markers
            
        return img_bgr, markers

    def _extract_name(self, img_bgr: np.ndarray, ML, MR, BL, BR) -> Tuple[str, str]:
        """Warp vùng dưới, crop padding, downscale và đọc chữ"""
        src_pts = np.float32([[ML['x'] + ML['w'], ML['y'] + ML['h']], [MR['x'], MR['y'] + MR['h']], [BR['x'], BR['y']], [BL['x'] + BL['w'], BL['y']]])
        dst_pts = np.float32([[0, 0], [self.warp_bot['width'], 0], [self.warp_bot['width'], self.warp_bot['height']], [0, self.warp_bot['height']]])
        
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        img_bot_warped = cv2.warpPerspective(img_bgr, matrix, (self.warp_bot['width'], self.warp_bot['height']))

        # Đã nới lỏng PADDING so với bản nháp để chống lẹm bong bóng
        PAD_TOP, PAD_BOTTOM, PAD_LEFT, PAD_RIGHT = 30, 66, 27, 24
        img_matrix_only = img_bot_warped[PAD_TOP:self.warp_bot['height'] - PAD_BOTTOM, PAD_LEFT:self.warp_bot['width'] - PAD_RIGHT]

        img_matrix_gray = cv2.cvtColor(img_matrix_only, cv2.COLOR_BGR2GRAY)
        _, img_matrix_bin = cv2.threshold(img_matrix_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        resized_40x26 = cv2.resize(img_matrix_bin, (40, 26), interpolation=cv2.INTER_AREA)

        # Khử nhiễu viền ngang bằng Median Subtraction
        row_medians = np.median(resized_40x26, axis=1, keepdims=True)
        clean_matrix = np.clip(resized_40x26 - row_medians, 0, 255)

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result_chars = []

        for col_idx in range(40):
            column_data = clean_matrix[:, col_idx]
            if np.max(column_data) == 0:
                result_chars.append(" ")
                continue
                
            d_max = np.max(column_data)
            col_mean, col_std = np.mean(column_data), np.std(column_data)
            
            # Ngưỡng Z-Score (cách biệt 3.5 độ lệch chuẩn) và điểm đen > 30
            if d_max > (col_mean + 3.5 * col_std) and d_max > 30:
                result_chars.append(alphabet[np.argmax(column_data)])
            else:
                result_chars.append(" ") 

        ho_lot = re.sub(r'\s+', ' ', "".join(result_chars[:20]).rstrip())
        ten = re.sub(r'\s+', ' ', "".join(result_chars[20:]).rstrip())
        return ho_lot, ten

    def process_warping(self, img_bgr_raw: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str, str]:
        try:
            img_bgr = self._ensure_portrait_orientation(img_bgr_raw)
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_binary_marker = self._preprocess_marker(img_gray)
            
            markers = self._find_6_markers(img_binary_marker)
            img_bgr, markers = self._check_upside_down_and_rotate(img_bgr, markers, img_binary_marker)
            TL, TR, ML, MR, BL, BR = markers
            
            # Warp Top (Phần OMR)
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_binary_marker = self._preprocess_marker(img_gray)
            img_binary_bubble = self._preprocess_bubble(img_gray)

            src_top = np.float32([[TL['x'], TL['y']], [TR['x'], TR['y']], [MR['x'], MR['y']], [ML['x'], ML['y']]])
            dst_top = np.float32([[0, 0], [self.warp_top['width'], 0], [self.warp_top['width'], self.warp_top['height']], [0, self.warp_top['height']]])
            matrix_top = cv2.getPerspectiveTransform(src_top, dst_top)
            size_top = (self.warp_top['width'], self.warp_top['height'])

            top_bgr = cv2.warpPerspective(img_bgr, matrix_top, size_top)
            top_bin = cv2.warpPerspective(img_binary_bubble, matrix_top, size_top)
            top_marker = cv2.warpPerspective(img_binary_marker, matrix_top, size_top)

            # Đọc Tên từ vùng Bot
            ho_lot, ten = self._extract_name(img_bgr, ML, MR, BL, BR)

            return top_bgr, top_bin, top_marker, ho_lot, ten

        except Exception as e:
            app_logger.error(f"Lỗi Warping: {e}")
            raise