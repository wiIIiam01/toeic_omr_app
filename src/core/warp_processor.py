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
        self.warp_top_4m = config.get('warp_top_4m_size', self.warp_top)

        self.scale_ref = self.prep_cfg.get('marker_scaling_ref', 0.0225)
        self.max_ref = self.prep_cfg.get('marker_max_ref', 0.15)
        self.aspect_range = self.prep_cfg.get('marker_aspect_ratio_range', [0.8, 1.2])
        self.min_density = self.prep_cfg.get('min_marker_density', 0.7)
        self.size_consistency = self.prep_cfg.get('marker_size_consistency', 0.5)

    def _preprocess_marker(self, img_gray: np.ndarray) -> np.ndarray:
        _, img_binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)
        return img_binary

    def _preprocess_bubble(self, img_gray: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img_gray = clahe.apply(img_gray)
        _, img_binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return img_binary

    @staticmethod
    def _sort_markers(markers: List[Dict]) -> List[Dict]:
        """Sắp theo hàng (cy) rồi trong mỗi cặp theo cx -> [TL, TR, ML, MR, (BL, BR)]."""
        by_y = sorted(markers, key=lambda m: m['cy'])
        ordered = []
        for i in range(0, len(by_y), 2):
            ordered.extend(sorted(by_y[i:i + 2], key=lambda m: m['cx']))
        return ordered

    @staticmethod
    def _is_landscape_layout(markers: List[Dict]) -> bool:
        xs = [m['cx'] for m in markers]
        ys = [m['cy'] for m in markers]
        return (max(xs) - min(xs)) > (max(ys) - min(ys))

    def _rotate_and_relocate(self, img_bgr, img_bin, rotate_code, expected_n):
        img_bgr = cv2.rotate(img_bgr, rotate_code)
        img_bin = cv2.rotate(img_bin, rotate_code)
        markers = self._find_markers(img_bin)
        if len(markers) != expected_n:
            raise ValueError(f"Sau khi xoay tìm thấy {len(markers)} marker, kỳ vọng {expected_n}.")
        return img_bgr, img_bin, markers

    def _ensure_expected_orientation(self, img_bgr, img_bin, markers):
        """6 marker -> bố cục phải DỌC; 4 marker -> bố cục phải NGANG. Sai thì xoay 90°."""
        n = len(markers)
        want_landscape = (n == 4)
        if self._is_landscape_layout(markers) != want_landscape:
            app_logger.debug(f"{n} markers: bố cục sai hướng, xoay 90°.")
            img_bgr, img_bin, markers = self._rotate_and_relocate(
                img_bgr, img_bin, cv2.ROTATE_90_CLOCKWISE, n)
        return img_bgr, img_bin, markers

    def _find_markers(self, img_binary_marker: np.ndarray) -> List[Dict[str, int]]:
        """Trả về 6 marker (A4 dọc) hoặc 4 marker (phôi gập). Chưa sắp xếp vai trò."""
        img_h, img_w = img_binary_marker.shape[:2]
        short_side = min(img_h, img_w)              # bất biến khi xoay 90°
        min_size = self.scale_ref * short_side
        max_size = self.max_ref * short_side

        contours, _ = cv2.findContours(img_binary_marker, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if not (min_size <= w <= max_size and min_size <= h <= max_size):
                continue
            if not (self.aspect_range[0] <= w / h <= self.aspect_range[1]):
                continue
            density = cv2.countNonZero(img_binary_marker[y:y + h, x:x + w]) / float(w * h)
            if density < self.min_density:
                continue
            candidates.append({'cx': x + w // 2, 'cy': y + h // 2,
                               'x': x, 'y': y, 'w': w, 'h': h, 'area': w * h})

        # Chọn nhóm n marker lớn nhất, đồng nhất kích thước, tách biệt rõ với ứng viên kế tiếp
        candidates.sort(key=lambda m: m['area'], reverse=True)
        for n in (6, 4):
            if len(candidates) < n:
                continue
            group = candidates[:n]
            largest = group[0]['area']
            if group[-1]['area'] / largest < self.size_consistency:
                continue                     # trong nhóm có phần tử quá nhỏ -> là nhiễu
            if len(candidates) > n and candidates[n]['area'] / largest >= self.size_consistency:
                continue                     # ứng viên thứ n+1 cũng giống marker -> mơ hồ
            return group

        raise ValueError(f"Tìm thấy {len(candidates)} ứng viên nhưng không xác định được "
                         f"nhóm 4 hoặc 6 marker đồng nhất. Hãy chụp lại rõ 4 góc phôi.")

    def _band_density(self, left_m: Dict, right_m: Dict, img_bin: np.ndarray) -> float:
        """Tỷ lệ pixel đen trong dải tứ giác nối mép trong của 2 marker cùng hàng."""
        pts = np.array([
            [left_m['x'] + left_m['w'], left_m['y']],
            [left_m['x'] + left_m['w'], left_m['y'] + left_m['h']],
            [right_m['x'],              right_m['y'] + right_m['h']],
            [right_m['x'],              right_m['y']],
        ], np.int32).reshape((-1, 1, 2))
        mask = np.zeros_like(img_bin)
        cv2.fillPoly(mask, [pts], 255)
        area = cv2.countNonZero(mask)
        if area == 0:
            return 0.0
        return cv2.countNonZero(cv2.bitwise_and(img_bin, mask)) / area

    def _check_upside_down_and_rotate(self, img_bgr, img_bin, markers):
        """Cặp marker có dải đậm đặc hơn (chứa 9 vạch định vị) là cạnh Top thật."""
        ordered = self._sort_markers(markers)
        d_top = self._band_density(ordered[0], ordered[1], img_bin)
        d_bot = self._band_density(ordered[-2], ordered[-1], img_bin)
        app_logger.debug(f"Band density: top={d_top:.3f}, bottom={d_bot:.3f}")
        if abs(d_top - d_bot) < 0.02:
            app_logger.warning("Mật độ 2 cạnh gần bằng nhau, kết quả chống ngược có thể không tin cậy.")

        if d_bot > d_top:
            app_logger.debug("Ảnh bị ngược. Xoay 180°.")
            img_bgr, img_bin, markers = self._rotate_and_relocate(
                img_bgr, img_bin, cv2.ROTATE_180, len(ordered))
            ordered = self._sort_markers(markers)
        return img_bgr, img_bin, ordered


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
            img_bgr = img_bgr_raw
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_binary_marker = self._preprocess_marker(img_gray)

            # 1. Tìm marker trên ảnh gốc (không ép xoay trước)
            markers = self._find_markers(img_binary_marker)
            n = len(markers)
            app_logger.debug(f"Phát hiện {n} markers ({'A4 dọc' if n == 6 else 'phôi gập'}).")

            # 2. Chuẩn hướng 90° theo bố cục marker, rồi chống ngược 180°
            img_bgr, img_binary_marker, markers = self._ensure_expected_orientation(
                img_bgr, img_binary_marker, markers)
            img_bgr, img_binary_marker, markers = self._check_upside_down_and_rotate(
                img_bgr, img_binary_marker, markers)
            TL, TR, ML, MR = markers[:4]

            # 3. Ảnh bong bóng: CLAHE + Otsu phải tính lại trên ảnh đã xoay
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_binary_bubble = self._preprocess_bubble(img_gray)

            # 4. Warp vùng Top (chung cho cả 2 loại phôi)
            ws = self.warp_top if n == 6 else self.warp_top_4m
            W_t, H_t = ws['width'], ws['height']
            src_top = np.float32([[TL['x'], TL['y']], [TR['x'], TR['y']],
                                  [MR['x'], MR['y']], [ML['x'], ML['y']]])
            dst_top = np.float32([[0, 0], [W_t, 0], [W_t, H_t], [0, H_t]])
            matrix_top = cv2.getPerspectiveTransform(src_top, dst_top)

            top_bgr = cv2.warpPerspective(img_bgr, matrix_top, (W_t, H_t))
            top_bin = cv2.warpPerspective(img_binary_bubble, matrix_top, (W_t, H_t))
            top_marker = cv2.warpPerspective(img_binary_marker, matrix_top, (W_t, H_t))

            # 5. Vùng tên: chỉ phôi 6 marker mới có
            if n == 6:
                BL, BR = markers[4], markers[5]
                ho_lot, ten = self._extract_name(img_bgr, ML, MR, BL, BR)
            else:
                ho_lot, ten = "", ""

            return top_bgr, top_bin, top_marker, ho_lot, ten

        except Exception as e:
            app_logger.error(f"Lỗi Warping: {e}")
            raise