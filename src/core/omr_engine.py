import cv2
import numpy as np
from typing import Tuple, Dict, Any, List
from src.utils.logger import app_logger
from src.utils.helpers import OMRUtils

class OMREngine:

    # --- CÁC HẰNG SỐ CẤU HÌNH CỨNG (HARDCODED SPECS) ---
    SCAN_THICKNESS = 50 
    
    # Thông số lọc nhiễu cho vạch định vị (Top Marks)
    X_MIN_SIZE = 19; X_MAX_SIZE = 29
    X_WH_RATIO_MIN = 0.8; X_WH_RATIO_MAX = 1.2 
    
    # Thông số lọc nhiễu cho hàng (Side Marks)
    Y_W_MIN = 22; Y_W_MAX = 32
    Y_H_MIN = 4; Y_H_MAX = 14 

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.OMR_CFG = config.get('ALGORITHM_CONFIG', {}).get('omr_engine', {})
        self.VIS_CFG = config.get('ALGORITHM_CONFIG', {}).get('visualization', {})
        app_logger.debug("OMREngine initialized.")

    def _detect_bubble_fill(self, img_binary: np.ndarray, center_x: int, center_y: int, R: int) -> Tuple[int, float]:
        """
        Logic xác định ô tô/không tô.
        """
        H, W = img_binary.shape
        min_fill_percentage = self.OMR_CFG.get('min_fill_percentage', 0.40)

        r_start = max(0, center_y - R)
        r_end = min(H, center_y + R)
        c_start = max(0, center_x - R)
        c_end = min(W, center_x + R)
    
        roi_h = r_end - r_start
        roi_w = c_end - c_start
    
        roi = img_binary[r_start:r_end, c_start:c_end]

        if roi.size == 0: return 0, 0.0

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

    def _find_top_marks(self, img_warped_marker: np.ndarray) -> List[Dict[str, int]]:
        """
        Tìm 9 vạch định vị ở biên trên.
        Trả về danh sách các dict chứa {center_x, w, h} để dùng cho cả việc tính R và Grid.
        """
        H, W = img_warped_marker.shape[:2]
        top_scan_slice = img_warped_marker[0:self.SCAN_THICKNESS, 0:W]
        contours_top, _ = cv2.findContours(top_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours_top = []
        for c in contours_top:
            x, y, w, h = cv2.boundingRect(c)
            ratio = w / h if h > 0 else 0
            # Logic lọc kích thước gốc
            if (self.X_MIN_SIZE <= w <= self.X_MAX_SIZE and 
                self.X_MIN_SIZE <= h <= self.X_MAX_SIZE and 
                self.X_WH_RATIO_MIN <= ratio <= self.X_WH_RATIO_MAX):
                valid_contours_top.append({'center_x': x + w // 2, 'w': w, 'h': h})
        
        if len(valid_contours_top) != 9:
             raise ValueError(f"❌ LỖI TEMPLATE: Biên trên tìm thấy {len(valid_contours_top)} bubble. YÊU CẦU 9.")

        valid_contours_top.sort(key=lambda item: item['center_x'])
        return valid_contours_top

    def _find_left_marks(self, img_warped_marker: np.ndarray) -> List[int]:
        """
        Tìm 25 vạch định vị ở biên trái.
        """
        H, W = img_warped_marker.shape[:2]
        left_scan_slice = img_warped_marker[0:H, 0:self.SCAN_THICKNESS]
        contours_left, _ = cv2.findContours(left_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours_left = []
        for c in contours_left:
            x, y, w, h = cv2.boundingRect(c)
            # Logic lọc kích thước gốc
            if (self.Y_W_MIN <= w <= self.Y_W_MAX and 
                self.Y_H_MIN <= h <= self.Y_H_MAX):
                valid_contours_left.append({'center_y': y + h // 2})
        
        if len(valid_contours_left) != 25:
             raise ValueError(f"❌ LỖI TEMPLATE: Biên trái tìm thấy {len(valid_contours_left)} hàng. YÊU CẦU 25.")        
        
        valid_contours_left.sort(key=lambda item: item['center_y'])
        return [item['center_y'] for item in valid_contours_left]

    def _calculate_radius_original(self, valid_top_marks: List[Dict[str, int]]) -> int:
        """
        Tính bán kính R dựa trên kích thước trung bình của các vạch Top.
        """
        NEW_BUBBLE_W = np.mean([item['w'] for item in valid_top_marks])
        NEW_BUBBLE_H = np.mean([item['h'] for item in valid_top_marks])
        R = int((NEW_BUBBLE_W + NEW_BUBBLE_H) / 4 - 1)
        return R

    def _interpolate_x_original(self, valid_top_marks: List[Dict[str, int]]) -> List[int]:
        """
        Nội suy tọa độ X cho 32 cột từ 9 vạch gốc.
        LOGIC GỐC: Sử dụng các biến S, U, LC, JUMP và list N.
        """
        FINAL_X_INDICES_9 = [item['center_x'] for item in valid_top_marks]
        
        S = FINAL_X_INDICES_9
        # Công thức nội suy đặc thù
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
        return FINAL_X_INDICES_32

    def process_omr(self, img_warped_marker: np.ndarray, img_warped_binary: np.ndarray, img_warped_bgr: np.ndarray) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """
        Hàm chính điều phối quy trình OMR.
        """
        try:
            # 1. Tìm Marks & Tính R & Nội suy Grid
            valid_top_marks = self._find_top_marks(img_warped_marker)
            R = self._calculate_radius_original(valid_top_marks)
            X_CENTERS = self._interpolate_x_original(valid_top_marks)
            Y_CENTERS = self._find_left_marks(img_warped_marker)
            
            # 2. Detect Bubble Fill
            rows = len(Y_CENTERS)
            cols = len(X_CENTERS)
            
            result_matrix = np.zeros((rows, cols), dtype=int)
            density_matrix = np.zeros((rows, cols), dtype=float)

            for i, center_y in enumerate(Y_CENTERS): 
                for j, center_x in enumerate(X_CENTERS): 
                    is_filled, density = self._detect_bubble_fill(img_warped_binary, center_x, center_y, R)
                    result_matrix[i, j] = is_filled
                    density_matrix[i, j] = density

            # 3. Mapping & Visualize
            image_with_grid = img_warped_bgr.copy() 
            answers_list = []
            groups = cols // 4
            
            # Config visualize
            threshold_high = self.VIS_CFG.get('threshold_high_density', 0.5)
            threshold_medium = self.VIS_CFG.get('threshold_medium_density', 0.4)
            color_high = tuple(self.VIS_CFG.get('color_high', [0, 255, 0]))
            color_medium = tuple(self.VIS_CFG.get('color_medium', [0, 255, 255]))
            color_low = tuple(self.VIS_CFG.get('color_low', [0, 165, 255]))

            for g in range(groups): 
                col_start = g * 4
                col_indices = list(range(col_start, col_start + 4))
                for r in range(rows): 
                    bits = tuple(int(result_matrix[r, c]) for c in col_indices)
                    densities = [density_matrix[r, c] for c in col_indices]
                    
                    # Logic chuyển đổi bits -> char (Dùng helper chung)
                    ch, final_bits = OMRUtils.bits_to_char(bits, densities)
                    answers_list.append(ch)
                    
                    # Visualize
                    if ch in ('A', 'B', 'C', 'D'):
                        marked_col_idx = col_indices[final_bits.index(1)] 
                        x = X_CENTERS[marked_col_idx]
                        y = Y_CENTERS[r]
                        density = density_matrix[r, marked_col_idx]

                        if density >= threshold_high:
                            cv2.circle(image_with_grid, (x, y), R - 2, color_high, -1)
                        elif density >= threshold_medium:
                            cv2.circle(image_with_grid, (x, y), R - 2, color_medium, -1)
                        else:
                            cv2.circle(image_with_grid, (x, y), R - 2, color_low, -1)
                    elif ch == '0':
                        pass

            app_logger.info(f"OMR Processed successfully. Extracted {len(answers_list)} answers.")
            return answers_list, result_matrix, image_with_grid

        except Exception as e:
            app_logger.error(f"Error in OMR Processing: {e}")
            raise