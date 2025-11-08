from typing import List, Dict, Any, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
import cv2
import datetime
from processing.utils import get_answer_parts_ranges 

class GradeManager:
    def __init__(self, key_answer: str, scoring_ref: Dict[str, Dict[int, int]], set_name: str, test_id: str): 
        self.key = self._process_key(key_answer)
        self.SCALING_REF = scoring_ref
        self.set_name = set_name
        self.test_id = test_id

    def _process_key(self, key_raw: str) -> str:
        processed_key = ''.join(key_raw.split())
        return processed_key
    
    def _scale_score(self, raw_score: int, part_type: str) -> int:
        scale_key = f"{part_type}_SCALE"
        raw_score = max(0, min(100, raw_score)) 
        return self.SCALING_REF.get(scale_key, {}).get(raw_score, 5)

    def grade_answers(self, answers_list: List[str]) -> Tuple[Dict[str, Any], List[int]]:
        n_answers = len(answers_list)
        n_key = len(self.key)
        
        if n_key != n_answers:
            raise ValueError(f"Độ dài key ({n_key}) và đáp án ({n_answers}) không khớp. Cần bằng nhau.")

        correct_list = [1 if answers_list[i] == self.key[i] else 0 for i in range(n_answers)]
        
        parts = {}
        LC_raw = 0
        RC_raw = 0
        ranges_1based = get_answer_parts_ranges()
        
        for idx, (a, b) in enumerate(ranges_1based, start=1):
            s = a - 1
            e = b
            correct = int(sum(correct_list[s:e]))
            parts[f"Part {idx}"] = correct
            
            if idx <= 4:
                LC_raw += correct
            else:
                RC_raw += correct
        
        LC_score = self._scale_score(LC_raw, 'LC')
        RC_score = self._scale_score(RC_raw, 'RC')
        Total_score = LC_score + RC_score
        
        parts['LC'] = LC_score
        parts['RC'] = RC_score
        parts['Total'] = Total_score
            
        return parts, correct_list

    def format_result(self, base_name: str, parts: Dict[str, int], answers_list: List[str]) -> Dict[str, Any]:
        answers_string = ''.join(answers_list)
        row_dict = {
            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Set": self.set_name,
            "Test": self.test_id,
            "Name": base_name,
            "Total": parts['Total'],
            "LC": f"{parts['LC']} / 495",
            "RC": f"{parts['RC']} / 495",
            "Part 1": f"{parts['Part 1']} / 6",
            "Part 2": f"{parts['Part 2']} / 25",
            "Part 3": f"{parts['Part 3']} / 39",
            "Part 4": f"{parts['Part 4']} / 30",
            "Part 5": f"{parts['Part 5']} / 30",
            "Part 6": f"{parts['Part 6']} / 16",
            "Part 7": f"{parts['Part 7']} / 54",
            "Reference": answers_string
        }
        return row_dict
        
    def save_result_image(self, base_name: str, image_with_grid: np.ndarray, result_dir: Path):
        result_dir.mkdir(exist_ok=True)
        save_img_path = result_dir / f"{base_name}_RESULT.png"
        ok = cv2.imwrite(str(save_img_path), image_with_grid)
        if not ok:
            raise RuntimeError(f"Lưu ảnh thất bại: {save_img_path}")
            
    def save_all_to_excel(self, all_results_list: List[Dict[str, Any]], result_xlsx: Path):
        excel_columns = [
            "Timestamp", "Set", "Test", "Name", 
            "Total", "LC", "RC", 
            "Part 1", "Part 2", "Part 3", "Part 4", 
            "Part 5", "Part 6", "Part 7", 
            "Reference"
        ]
        df = pd.DataFrame(all_results_list, columns=excel_columns)
        df.to_excel(result_xlsx, index=False)