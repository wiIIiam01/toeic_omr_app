import cv2
import numpy as np
from typing import Tuple, Dict, Any, List
from src.utils.logger import app_logger

class OMREngine:

    SCAN_THICKNESS = 50 
    
    # Thông số lọc nhiễu cho vạch định vị (Top Marks)
    X_MIN_SIZE = 19; X_MAX_SIZE = 29
    X_WH_RATIO_MIN = 0.8; X_WH_RATIO_MAX = 1.2 
    
    # Thông số lọc nhiễu cho hàng (Side Marks)
    Y_W_MIN = 22; Y_W_MAX = 32
    Y_H_MIN = 4; Y_H_MAX = 14 
 
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.VIS_CFG = config.get('ALGORITHM_CONFIG', {}).get('visualization', {})
        app_logger.debug("OMREngine initialized.")

    def _fill_density(self, img_binary: np.ndarray, center_x: int, center_y: int, R: int) -> float:
        """
        Lấy giá trị density (độ đậm) của ô.
        """
        H, W = img_binary.shape
        r_start = max(0, center_y - R)
        r_end = min(H, center_y + R)
        c_start = max(0, center_x - R)
        c_end = min(W, center_x + R)
    
        roi = img_binary[r_start:r_end, c_start:c_end]

        if roi.size == 0: return 0.0
        
        roi_h = r_end - r_start
        roi_w = c_end - c_start

        mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        roi_center_x = roi_w // 2
        roi_center_y = roi_h // 2
    
        cv2.circle(mask, (roi_center_x, roi_center_y), R-2, 255, -1) 
    
        masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
        total_circle_pixels = np.sum(mask == 255) 
        filled_pixels_in_circle = np.sum(masked_roi == 255) 
    
        if total_circle_pixels == 0:
            return 0.0
        
        return filled_pixels_in_circle / total_circle_pixels
    
    def _read_answers(self, density_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Input: Ma trận density của 25x32 bubbles
        Output: 
            - answers_grid: (25, 8) chứa ký tự 'A', 'B'...
            - confidences_grid: (25, 8) chứa float
        """
        rows, cols = density_matrix.shape
        
        # 1. Reshape thành (Rows, Groups, 4 Answers)
        # Giữ nguyên cấu trúc không gian của ảnh
        questions_grid = density_matrix.reshape(rows, -1, 4) 
        
        # 2. Sắp xếp trên trục cuối cùng (axis=2)
        sorted_idx = np.argsort(questions_grid, axis=2)
        sorted_d = np.take_along_axis(questions_grid, sorted_idx, axis=2)

        d_min = sorted_d[:, :, 0]
        d_2nd = sorted_d[:, :, 2]
        d_max = sorted_d[:, :, 3]
        
        range_val = d_max - d_min
        std_dev = np.std(questions_grid, axis=2)

        THRESHOLD_RANGE = 0.15
        has_answer_mask = range_val >= THRESHOLD_RANGE

        # Tính Confidence
        conf_filled = (d_max - d_2nd) / (range_val + 1e-9)
        MIN_SIGMA = 0.05
        conf_filled = np.where(std_dev < MIN_SIGMA, 0.0, conf_filled)
        
        PENALTY = 10.0
        conf_empty = 1.0 - (std_dev * PENALTY)
        
        confidences = np.where(has_answer_mask, conf_filled, conf_empty)
        confidences = np.clip(confidences, 0.0, 1.0) 

        # Chọn ký tự
        char_map = np.array(['A', 'B', 'C', 'D'])
        max_col_indices = sorted_idx[:, :, 3]
        predicted_chars = char_map[max_col_indices]
        
        answers = np.where(has_answer_mask, predicted_chars, '0')

        return answers, confidences
    
    def _draw_centered_text(self, img, text, x, y, font_scale, color, thickness):
        """Hàm hỗ trợ vẽ text căn giữa tại toạ độ (x, y)"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = int(x - text_size[0] / 2)
        text_y = int(y + text_size[1] / 2)
        cv2.putText(img, text, (text_x, text_y), font, font_scale, color, thickness)

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
        return int((NEW_BUBBLE_W + NEW_BUBBLE_H) / 4 - 1)

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

    def process_omr(self, answer_key: str, img_warped_marker: np.ndarray, img_warped_binary: np.ndarray, img_warped_bgr: np.ndarray) -> Tuple[List[str], np.ndarray, Dict[str, Any]]:
        """
        Hàm chính điều phối quy trình OMR.
        """
        try:
            # 1. Tìm Marks & Tính R & Nội suy Grid
            valid_top_marks = self._find_top_marks(img_warped_marker)
            R = self._calculate_radius_original(valid_top_marks)
            X_CENTERS = self._interpolate_x_original(valid_top_marks)
            Y_CENTERS = self._find_left_marks(img_warped_marker)
            
            # 2. Detect Density
            rows = len(Y_CENTERS)
            cols = len(X_CENTERS)

            density_matrix = np.zeros((rows, cols), dtype=float)

            for i, center_y in enumerate(Y_CENTERS): 
                for j, center_x in enumerate(X_CENTERS): 
                    density = self._fill_density(img_warped_binary, center_x, center_y, R)
                    density_matrix[i, j] = density

            # 3. XỬ LÝ VECTOR HÓA (Nhận về Grid 25x8)
            answers_grid, conf_grid = self._read_answers(density_matrix)

            # 4. VISUALIZE (Duyệt theo đúng tọa độ r, g)
            color_high = tuple(self.VIS_CFG.get('color_high', [0, 255, 0]))
            color_medium = tuple(self.VIS_CFG.get('color_medium', [0, 215, 255]))
            color_low = tuple(self.VIS_CFG.get('color_low', [0, 80, 255]))
            color_text = tuple(self.VIS_CFG.get('color_text', [0, 0, 0]))
            color_text_alert = tuple(self.VIS_CFG.get('color_text_alert', [0, 0, 255]))
            color_correct = (0, 255, 0)
            color_wrong = (0, 80, 255)
            
            image_with_grid = img_warped_bgr.copy() 
            
            groups = cols // 4 
            
            for r in range(rows):       # Duyệt hàng
                for g in range(groups): # Duyệt nhóm
                    
                    q_idx = (g * rows) + r
                    ans_char = answers_grid[r, g]
                        
                    if q_idx < len(answer_key):
                        correct_char = answer_key[q_idx]
                        
                        if correct_char in ['A', 'B', 'C', 'D']:
                            # Tìm toạ độ vẽ
                            key_char_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(correct_char)
                            key_col = (g * 4) + key_char_idx
                            
                            x_key = X_CENTERS[key_col]
                            y_key = Y_CENTERS[r]
                            
                            if correct_char == ans_char:
                                color = color_correct
                            else:
                                color = color_wrong
                            # Vẽ vòng tròn rỗng (thickness = 2), bán kính to hơn bubble chút (R+4)
                            cv2.circle(image_with_grid, (x_key, y_key), R-3, color, 2)
                
                    # Truy xuất trực tiếp theo tọa độ (r, g) -> Cực kỳ an toàn
                    confidence = conf_grid[r, g]
                    conf_text = f"{int(confidence * 100)}"
                    
                    # Lấy tọa độ X, Y để vẽ
                    col_start = g * 4
                    col_indices = list(range(col_start, col_start + 4))
                    
                    if ans_char in ('A', 'B', 'C', 'D'):
                        char_map_idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(ans_char)
                        marked_col = col_indices[char_map_idx]
                        x = X_CENTERS[marked_col]
                        y = Y_CENTERS[r]
                        
                        # Logic màu sắc
                        if confidence >= 0.7: bubble_color = color_high
                        elif confidence >= 0.25: bubble_color = color_medium
                        else: bubble_color = color_low

                        cv2.circle(image_with_grid, (x, y), R - 2, bubble_color, -1)
                        self._draw_centered_text(image_with_grid, conf_text, x, y, 0.4, color_text, 1)

                    else: 
                        col_A = col_indices[0]
                        x_A = X_CENTERS[col_A]
                        y_A = Y_CENTERS[r]
                        self._draw_centered_text(image_with_grid, conf_text, x_A, y_A, 0.4, color_text_alert, 1)

            # 5. XUẤT KẾT QUẢ (FLATTEN ĐỂ TRẢ VỀ LIST)
            # Input: (25 hàng, 8 nhóm) -> Transpose thành (8 nhóm, 25 hàng) -> Flatten thành 200 câu
            answers_list = answers_grid.T.flatten().tolist()
            confidences_list = conf_grid.T.flatten().tolist()

            # Thống kê
            stats = {
                'confidences_list': confidences_list,
                'confidence': float(np.mean(confidences_list)) if confidences_list else 0.0,
                'lowest_conf': float(np.min(confidences_list)) if confidences_list else 0.0,
                'lowest_conf_index': int(np.argmin(confidences_list)) if confidences_list else -1
            }
            
            app_logger.info(f"OMR Success. Answers: {len(answers_list)} | "
                            f"Avg Conf: {stats['confidence']:.2f} | "
                            f"Min Conf: {stats['lowest_conf']:.2f}")
            return answers_list, image_with_grid, stats

        except Exception as e:
            app_logger.error(f"Error in OMR Processing: {e}")
            raise