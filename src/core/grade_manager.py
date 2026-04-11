import json
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
                 set_name: str, test_id: str, test_date: str = "", class_name: str = ""):
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
        self.class_name = class_name
        self.test_date = test_date
        self.weight_matrix = self._load_skill_matrix()
        app_logger.debug(f"GradeManager initialized for Test ID: {test_id} (Length: {len(self.key)})")

    def _load_skill_matrix(self) -> np.ndarray:
        #Đọc JSON thành NumPy array, trả về None nếu file không tồn tại.
        matrix_path = Path(f"config/skill_matrices/{self.set_name.replace(" ", "")}_{self.test_id}.json")
        if not matrix_path.exists():
            app_logger.error(f"Lỗi không tìm thấy {matrix_path}")
            return None
        try:
            with open(matrix_path, 'r', encoding='utf-8') as f:
                return np.array(json.load(f), dtype=float)
        except Exception as e:
            app_logger.error(f"Lỗi đọc ma trận kỹ năng đề {self.test_id}: {e}")
            return None
        
    def _calculate_skills(self, correct_vector: List[int]) -> Dict[str, float]:
        """Thực hiện nhân ma trận trên RAM."""
        skill_keys = ['lc_1', 'lc_2', 'lc_3', 'lc_4', 'rc_1', 'rc_2', 'rc_3', 'rc_4', 'rc_5']
        
        if self.weight_matrix is None:
            return {k: 0.0 for k in skill_keys}

        try:
            vec = np.array(correct_vector, dtype=float)
            if len(vec) != self.weight_matrix.shape[0]:
                vec = np.pad(vec, (0, max(0, self.weight_matrix.shape[0] - len(vec))))[:self.weight_matrix.shape[0]]

            achieved_scores = vec.dot(self.weight_matrix)
            max_scores = self.weight_matrix.sum(axis=0)
            
            ratios = np.zeros_like(achieved_scores, dtype=float)
            np.divide(achieved_scores, max_scores, out=ratios, where=max_scores!=0)
            
            return {skill_keys[i]: round(float(ratios[i]), 2) for i in range(9)}

        except Exception as e:
            app_logger.error(f"Lỗi tính toán: {e}")
            return {k: 0.0 for k in skill_keys}

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

    def grade_answers(self, user_answers: List[str]) -> Dict[str, Any]:
        """
        Chấm điểm chi tiết.
        
        Returns:
            parts_stats (Dict): Điểm số từng phần (Part 1-7, LC, RC, Total) và các nhóm kỹ năng.
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
            
            parts_stats[f"part_{idx}"] = correct_count
            
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
        skill_stats = self._calculate_skills(correct_vector)
        parts_stats.update(skill_stats)
        
        app_logger.info(f"Grading finished. Score: {total_score} (LC: {lc_score}, RC: {rc_score})")
        return parts_stats

    def format_result(self, base_name: str, parts: Dict[str, int], answers_list: List[str], conf_stats: Dict[str, Any] = None, process_time: float=0.0) -> Dict[str, Any]:
        """Tạo dictionary kết quả để lưu vào CSV."""
        answers_string = ''.join(answers_list)
        
        # Format theo yêu cầu báo cáo
        row_dict = {
            "Date": self.test_date,
            "Class": self.class_name,
            "Set": self.set_name,
            "Test": self.test_id,
            "Name": base_name,
            "Total": parts['Total'],
            "LC": parts['LC'],
            "RC": parts['RC'],
            "part_1": parts['part_1'],
            "part_2": parts['part_2'],
            "part_3": parts['part_3'],
            "part_4": parts['part_4'],
            "part_5": parts['part_5'],
            "part_6": parts['part_6'],
            "part_7": parts['part_7'],
            "lc_skill_1": parts['lc_1'],
            "lc_skill_2": parts['lc_2'],
            "lc_skill_3": parts['lc_3'],
            "lc_skill_4": parts['lc_4'],
            "rc_skill_1": parts['rc_1'],
            "rc_skill_2": parts['rc_2'],
            "rc_skill_3": parts['rc_3'],
            "rc_skill_4": parts['rc_4'],
            "rc_skill_5": parts['rc_5'],
            "detected_ans": answers_string,
            "conf": conf_stats.get('confidences_list', []),
            "process_time": process_time,
            "ground_truth": answers_string,
            "is_reviewed": False
        }
        # 1. Dành cho UI
        row_dict['Confidence'] = conf_stats.get('confidence', 0.0)
        row_dict['LowestConf'] = conf_stats.get('lowest_conf', 0.0)
        
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