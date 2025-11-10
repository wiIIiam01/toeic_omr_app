from typing import List, Dict, Any, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
import cv2
import datetime
from processing.utils import get_answer_parts_ranges 

class GradeManager:
    def __init__(self, key_answer: str, scoring_ref: Dict[str, Dict[int, int]], set_name: str, test_id: str, test_date_str: str = ""): 
        self.key = self._process_key(key_answer)
        self.SCALING_REF = scoring_ref
        self.set_name = set_name
        self.test_id = test_id
        self.test_date_str = test_date_str

    def _process_key(self, key_raw: str) -> str:
        processed_key = ''.join(key_raw.split())
        return processed_key
    
    def _scale_score(self, raw_score: int, part_type: str) -> int:
        scale_key = f"{part_type}_SCALE"
        raw_score = max(0, min(100, raw_score)) 
        return self.SCALING_REF.get(scale_key, {}).get(raw_score, 5)

    def get_result_dir(self) -> Path:
        date_to_format = self.test_date_str
        
        if not date_to_format:
            date_to_format = datetime.datetime.now().strftime("%Y-%m-%d")

        try:
            if len(date_to_format) > 10:
                 date_str_formatted = datetime.datetime.strptime(date_to_format.split()[0], "%Y-%m-%d").strftime("%Y-%m-%d")
            elif len(date_to_format) == 10:
                date_str_formatted = datetime.datetime.strptime(date_to_format, "%Y-%m-%d").strftime("%Y-%m-%d")
            else:
                date_str_formatted = datetime.datetime.now().strftime("%Y-%m-%d")
        except ValueError:
            date_str_formatted = datetime.datetime.now().strftime("%Y-%m-%d")

        folder_name = f"{self.set_name}_{self.test_id}_{date_str_formatted}"
        safe_folder_name = folder_name.replace(" ", "_").replace("/", "-").replace("\\", "-")
        
        result_dir = Path("log") / safe_folder_name
        result_dir.mkdir(parents=True, exist_ok=True)
        return result_dir

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
        if self.test_date_str:
            timestamp_value = self.test_date_str
        else:
            timestamp_value = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        answers_string = ''.join(answers_list)
        row_dict = {
            "Timestamp": timestamp_value,
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
        save_img_path = result_dir / f"{base_name}_LOG.png"
        ok = cv2.imwrite(str(save_img_path), image_with_grid)
        if not ok:
            raise RuntimeError(f"Lưu ảnh thất bại: {save_img_path}")
            
    def save_excel(self, all_results_list: List[Dict[str, Any]], result_dir: Path):
        if not all_results_list:
            return # Không có gì để lưu
        
        df_new = pd.DataFrame(all_results_list)
        excel_path = result_dir / f"{self.set_name}_{self.test_id}_Grading_Summary.xlsx"
        
        if excel_path.exists():
            # Nếu file đã tồn tại, đọc file cũ và nối dữ liệu (append)
            try:
                df_old = pd.read_excel(excel_path)
                # Đảm bảo cột Timestamp là chuỗi trước khi nối để tránh lỗi format
                df_old['Timestamp'] = df_old['Timestamp'].astype(str)
                df_new['Timestamp'] = df_new['Timestamp'].astype(str)
                df_combined = pd.concat([df_old, df_new], ignore_index=True)
                
            except Exception as e:
                # Nếu có lỗi khi đọc, coi như df_combined là df_new (ghi đè file cũ)
                print(f"Lỗi khi đọc file Excel cũ, ghi file mới. Lỗi: {e}")
                df_combined = df_new
        else:
            df_combined = df_new

        try:
            df_combined.to_excel(excel_path, index=False)
            print(f"Đã lưu/cập nhật tổng hợp kết quả tại: {excel_path}")
        except Exception as e:
            print(f"Lỗi khi lưu file Excel: {e}")