import cv2
import numpy as np
from typing import Tuple, Dict, Any, List
from processing.utils import bits_to_char

class OMREngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.OMR_CFG = config.get('omr_engine', {})
        self.VIS_CFG = config.get('visualization', {})

    def _detect_bubble(self, img_binary: np.ndarray, center_x: int, center_y: int, R: int) -> Tuple[int, float]:
        H, W = img_binary.shape
        min_fill_percentage = self.OMR_CFG.get('min_fill_percentage', 0.40)

        r_start = max(0, center_y - R)
        r_end = min(H, center_y + R)
        c_start = max(0, center_x - R)
        c_end = min(W, center_x + R)
    
        roi_h = r_end - r_start
        roi_w = c_end - c_start
    
        roi = img_binary[r_start:r_end, c_start:c_end]

        mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    
        roi_center_x = roi_w // 2
        roi_center_y = roi_h // 2
    
        cv2.circle(mask, (roi_center_x, roi_center_y), R-2, 255, -1) 
    
        masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
        total_circle_pixels = np.sum(mask == 255) 
        filled_pixels_in_circle = np.sum(masked_roi == 255) 
    
        if total_circle_pixels == 0:
            return 0, 0.0
        
        fill_ratio = filled_pixels_in_circle / total_circle_pixels
        is_filled = 1 if fill_ratio >= min_fill_percentage else 0
        return is_filled, fill_ratio

    def _generate_grid_and_detect(self, img_warped_binary: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[float],List[float], float]:
        H_new, W_new = img_warped_binary.shape[:2]
        SCAN_THICKNESS = 50 
        
        X_MIN_SIZE = 19; X_MAX_SIZE = 29; X_WH_RATIO_MIN = 0.8; X_WH_RATIO_MAX = 1.2 
        Y_W_MIN = 22; Y_W_MAX = 32; Y_H_MIN = 4; Y_H_MAX = 14 
        
        top_scan_slice = img_warped_binary[0:SCAN_THICKNESS, 0:W_new]
        contours_top, _ = cv2.findContours(top_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours_top = []
        for c in contours_top:
            x, y, w, h = cv2.boundingRect(c)
            ratio = w / h if h > 0 else 0
            if (X_MIN_SIZE <= w <= X_MAX_SIZE and X_MIN_SIZE <= h <= X_MAX_SIZE and X_WH_RATIO_MIN <= ratio <= X_WH_RATIO_MAX):
                valid_contours_top.append({'center_x': x + w // 2, 'w': w, 'h': h})
                
        if len(valid_contours_top) != 9:
             raise ValueError(f"❌ LỖI TEMPLATE: Biên trên tìm thấy {len(valid_contours_top)} bubble. YÊU CẦU 9.")

        valid_contours_top.sort(key=lambda item: item['center_x'])
        FINAL_X_INDICES_9 = [item['center_x'] for item in valid_contours_top]
        
        left_scan_slice = img_warped_binary[0:H_new, 0:SCAN_THICKNESS]
        contours_left, _ = cv2.findContours(left_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours_left = []
        for c in contours_left:
            x, y, w, h = cv2.boundingRect(c)
            if (Y_W_MIN <= w <= Y_W_MAX and Y_H_MIN <= h <= Y_H_MAX):
                valid_contours_left.append({'center_y': y + h // 2})
        
        if len(valid_contours_left) != 25:
             raise ValueError(f"❌ LỖI TEMPLATE: Biên trái tìm thấy {len(valid_contours_top)} hàng. YÊU CẦU 25.")        
        valid_contours_left.sort(key=lambda item: item['center_y'])
        FINAL_Y_INDICES = [item['center_y'] for item in valid_contours_left]

        NEW_BUBBLE_W = np.mean([item['w'] for item in valid_contours_top])
        NEW_BUBBLE_H = np.mean([item['h'] for item in valid_contours_top])
        R = int((NEW_BUBBLE_W + NEW_BUBBLE_H) / 4 - 1)
        
        S = FINAL_X_INDICES_9
        U = np.mean([S[5] - S[4], S[3] - S[2], S[2] - S[1]])
        LC = np.mean([(S[6] - S[0]) / 3, S[7] - S[5]])
        JUMP = S[8] - S[1]
        
        N = []
        N.append((S[1] + S[0]) / 2)
        N.extend([S[1], S[2], S[3]])
        X_1_4 = N[:4] 
        N.extend([LC + x for x in X_1_4])
        N.extend([S[4], S[5]])
        N.append(N[-1] + U)
        N.append(N[-1] + U) 
        N.extend([S[7] - U, S[7], S[7] + U, S[7] + 2 * U])
        X_1_16 = N[:16]
        N.extend([JUMP + x for x in X_1_16])
        FINAL_X_INDICES_32 = [int(x) for x in N]

        result_matrix = np.zeros((len(FINAL_Y_INDICES), len(FINAL_X_INDICES_32)), dtype=int)
        density_matrix = np.zeros((len(FINAL_Y_INDICES), len(FINAL_X_INDICES_32)), dtype=float)

        for i, center_y in enumerate(FINAL_Y_INDICES): 
            for j, center_x in enumerate(FINAL_X_INDICES_32): 
                is_filled, density = self._detect_bubble(img_warped_binary, center_x, center_y, R)
                result_matrix[i, j] = is_filled
                density_matrix[i, j] = density
                
        return result_matrix, density_matrix, FINAL_X_INDICES_32, FINAL_Y_INDICES, R

    def process_omr(self, img_warped_binary: np.ndarray, img_warped_bgr: np.ndarray) -> Tuple[List[str], np.ndarray, np.ndarray]:
        
        result_matrix, density_matrix, X_CENTERS, Y_CENTERS, R = self._generate_grid_and_detect(img_warped_binary)
        
        image_with_grid = img_warped_bgr.copy() 

        rows, cols = result_matrix.shape
        answers_list = []
        groups = cols // 4
        
        threshold_high = self.VIS_CFG.get('threshold_high_density', 0.5)
        threshold_medium = self.VIS_CFG.get('threshold_medium_density', 0.4)
        
        color_high = tuple(self.VIS_CFG.get('color_high', [0, 255, 0]))
        color_medium = tuple(self.VIS_CFG.get('color_medium', [0, 255, 255]))
        color_low = tuple(self.VIS_CFG.get('color_low', [0, 165, 255]))
        color_error = tuple(self.VIS_CFG.get('color_error', [0, 50, 255]))

        for g in range(groups): 
            col_start = g * 4
            col_indices = list(range(col_start, col_start + 4))
            for r in range(rows): 
                bits = tuple(int(result_matrix[r, c]) for c in col_indices)
                ch = bits_to_char(bits)
                answers_list.append(ch)
                
                if ch in ('A', 'B', 'C', 'D'):
                    marked_col_idx = col_indices[bits.index(1)] 
                    x = X_CENTERS[marked_col_idx]
                    y = Y_CENTERS[r]
                    density = density_matrix[r, marked_col_idx] # Lấy Density của bubble đã chọn

                    if density >= threshold_high:
                        cv2.circle(image_with_grid, (x, y), R - 2, color_high, -1)
                    elif density >= threshold_medium:
                        cv2.circle(image_with_grid, (x, y), R - 2, color_medium, -1)
                    else:
                        cv2.circle(image_with_grid, (x, y), R - 2, color_low, -1)
                    
                elif ch == 'X':
                    marked_col_indices = [col_indices[i] for i, bit in enumerate(bits) if bit == 1]
                    for marked_col_idx in marked_col_indices:
                        cx = X_CENTERS[marked_col_idx]
                        cy = Y_CENTERS[r]
                        cv2.circle(image_with_grid, (cx, cy), R - 2, color_error, -1)

        return answers_list, result_matrix, image_with_grid