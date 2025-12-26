from typing import List, Dict, Any, Tuple
from pathlib import Path
import cv2
import numpy as np
from src.utils import app_logger, OMRUtils

class GradeManager:
    """
    Quản lý logic chấm điểm:
    1. So khớp đáp án người dùng với đáp án chuẩn (Key).
    2. Quy đổi điểm thô (Raw Score) sang điểm chuẩn TOEIC (Scaled Score).
    3. Định dạng dữ liệu để xuất báo cáo.
    4. Lưu ảnh kết quả chấm.
    """

    def __init__(self, key_answer: str, scoring_ref: Dict[str, Dict[int, int]], 
                 set_name: str, test_id: str, test_date: str = ""):
        """
        Args:
            key_answer: Chuỗi đáp án chuẩn (VD: "ABCD...").
            scoring_ref: Bảng quy đổi điểm (Loaded từ JSON).
            set_name, test_id, test_date: Metadata của bài thi.
        """
        self.key = self._process_key(key_answer)
        self.scoring_ref = scoring_ref
        self.set_name = set_name
        self.test_id = test_id
        self.test_date = test_date
        
        app_logger.debug(f"GradeManager initialized for Test ID: {test_id} (Length: {len(self.key)})")

    def _process_key(self, key_raw: str) -> str:
        """Làm sạch chuỗi đáp án (xóa khoảng trắng, xuống dòng)."""
        if not key_raw:
            return ""
        return ''.join(key_raw.split())
    
    def _scale_score(self, raw_score: int, part_type: str) -> int:
        """
        Quy đổi điểm thô sang điểm TOEIC (5-495).
        Args:
            raw_score: Số câu đúng.
            part_type: 'LC' (Listening) hoặc 'RC' (Reading).
        """
        scale_key = f"{part_type}_SCALE"
        
        # Đảm bảo raw_score nằm trong giới hạn hợp lệ (0-100)
        safe_raw_score = max(0, min(100, raw_score))
        
        # Lấy bảng điểm con
        scale_dict = self.scoring_ref.get(scale_key, {})
        
        # Tra cứu điểm. Mặc định là 5 điểm nếu không tìm thấy.
        scaled_score = scale_dict.get(safe_raw_score, 5)
        return scaled_score

    def grade_answers(self, user_answers: List[str]) -> Tuple[Dict[str, Any], List[int]]:
        """
        Chấm điểm chi tiết.
        
        Returns:
            parts_stats (Dict): Điểm số từng phần (Part 1-7, LC, RC, Total).
            correct_vector (List[int]): Danh sách 0/1 (0: Sai, 1: Đúng) cho từng câu.
        """
        n_answers = len(user_answers)
        n_key = len(self.key)
        
        # Validate độ dài
        if n_key != n_answers:
            app_logger.error(f"Mismatch length! Key: {n_key}, User: {n_answers}")
            # Vẫn cố gắng chấm dựa trên độ dài ngắn nhất để không crash
            min_len = min(n_key, n_answers)
        else:
            min_len = n_key

        # So khớp đáp án (Tạo vector 0/1)
        correct_vector = [1 if user_answers[i] == self.key[i] else 0 for i in range(min_len)]
        
        # Nếu user_answers ngắn hơn key, phần còn lại coi như sai (0)
        if n_answers < n_key:
            correct_vector.extend([0] * (n_key - n_answers))

        parts_stats = {}
        lc_raw = 0
        rc_raw = 0
        
        # Lấy range câu hỏi cho Part 1-7 từ Utils
        ranges_1based = OMRUtils.get_answer_parts_ranges()
        
        for idx, (start_1b, end_1b) in enumerate(ranges_1based, start=1):
            # Chuyển sang 0-based index
            s = start_1b - 1
            e = end_1b
            
            # Tính số câu đúng trong range này
            # Lưu ý: cần handle trường hợp lát cắt vượt quá độ dài vector
            segment = correct_vector[s:e]
            correct_count = int(sum(segment))
            
            parts_stats[f"Part {idx}"] = correct_count
            
            # Cộng dồn vào LC (Part 1-4) hoặc RC (Part 5-7)
            if idx <= 4:
                lc_raw += correct_count
            else:
                rc_raw += correct_count
        
        # Quy đổi điểm
        lc_score = self._scale_score(lc_raw, 'LC')
        rc_score = self._scale_score(rc_raw, 'RC')
        total_score = lc_score + rc_score
        
        parts_stats['LC'] = lc_score
        parts_stats['RC'] = rc_score
        parts_stats['Total'] = total_score
        
        app_logger.info(f"Grading finished. Score: {total_score} (LC: {lc_score}, RC: {rc_score})")
        return parts_stats, correct_vector

    def format_result(self, base_name: str, parts: Dict[str, int], answers_list: List[str]) -> Dict[str, Any]:
        """Tạo dictionary kết quả để lưu vào Excel."""
        answers_string = ''.join(answers_list)
        
        # Format theo yêu cầu báo cáo
        row_dict = {
            "Date": self.test_date,
            "Set": self.set_name,
            "Test": self.test_id,
            "Name": base_name,
            "Total": parts['Total'],
            "LC": parts['LC'],
            "RC": parts['RC'],
            "Part 1": parts['Part 1'],
            "Part 2": parts['Part 2'],
            "Part 3": parts['Part 3'],
            "Part 4": parts['Part 4'],
            "Part 5": parts['Part 5'],
            "Part 6": parts['Part 6'],
            "Part 7": parts['Part 7'],
            "Reference": answers_string
        }
        return row_dict
        
    def save_result_image(self, base_name: str, image: np.ndarray, result_dir: Path) -> bool:
        """
        Lưu ảnh kết quả (đã visualize) xuống đĩa.
        """
        try:
            if not result_dir.exists():
                result_dir.mkdir(parents=True, exist_ok=True)
                
            save_path = result_dir / f"{base_name}.png"
            
            # Sử dụng cv2.imencode để hỗ trợ đường dẫn tiếng Việt (Windows)
            # cv2.imwrite thường lỗi với unicode path trên Windows
            success, buffer = cv2.imencode(".png", image)
            if success:
                with open(save_path, "wb") as f:
                    f.write(buffer)
                app_logger.debug(f"Saved result image: {save_path.name}")
                return True
            else:
                app_logger.error("Failed to encode image for saving.")
                return False
                
        except Exception as e:
            app_logger.error(f"Error saving result image {base_name}: {e}")
            return False