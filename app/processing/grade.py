from typing import List, Dict, Any, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
import cv2
from processing.utils import get_answer_parts_ranges 

class GradeManager:
    def __init__(self, key_answer: str): 
        self.key = self._process_key(key_answer)

    def _process_key(self, key_raw: str) -> str:
        processed_key = ''.join(key_raw.split())
        return processed_key

    def grade_answers(self, answers_list: List[str]) -> Tuple[Dict[str, Any], List[int]]:
        n_answers = len(answers_list)
        n_key = len(self.key)
        
        if n_key != n_answers:
            raise ValueError(f"Độ dài key ({n_key}) và đáp án ({n_answers}) không khớp. Cần bằng nhau.")

        correct_list = [1 if answers_list[i] == self.key[i] else 0 for i in range(n_answers)]
        
        parts = {}
        ranges_1based = get_answer_parts_ranges()
        
        for idx, (a, b) in enumerate(ranges_1based, start=1):
            s = a - 1
            e = b
            parts[f"part{idx}"] = int(sum(correct_list[s:e]))
            
        return parts, correct_list

    def format_result(self, base_name: str, parts: Dict[str, int], answers_list: List[str]) -> Dict[str, Any]:
        answers_string = ''.join(answers_list)
        row_dict = {
            "name": base_name,
            **parts, 
            "answer": answers_string
        }
        return row_dict
        
    def save_result_image(self, base_name: str, image_with_grid: np.ndarray, result_dir: Path):
        result_dir.mkdir(exist_ok=True)
        save_img_path = result_dir / f"{base_name}_RESULT.png"
        ok = cv2.imwrite(str(save_img_path), image_with_grid)
        if not ok:
            raise RuntimeError(f"Lưu ảnh thất bại: {save_img_path}")
            
    def save_all_to_excel(self, all_results_list: List[Dict[str, Any]], result_xlsx: Path):
        excel_columns = ["name", "part1", "part2", "part3", "part4", "part5", "part6", "part7", "answer"]
        df = pd.DataFrame(all_results_list, columns=excel_columns)
        df.to_excel(result_xlsx, index=False)