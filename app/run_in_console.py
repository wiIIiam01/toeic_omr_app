import cv2
import os
import numpy as np
from pathlib import Path
from datetime import datetime
from processing.utils import load_config, load_key, get_answer_key, load_scoring_ref, save_results_to_excel
from processing.warp import WarpingProcessor
from processing.omr_engine import OMREngine
from processing.grade import GradeManager
from typing import Dict, Tuple

KEY_PATH = Path("key.json")
SCORING_REF_PATH = 'scoring_ref.json'

def get_user_selection(key_data: Dict[str, Dict[str, str]]) -> Tuple[str, str, str]:
    set_names = list(key_data.keys())
    print("\n--- CHỌN BỘ ĐỀ ---")
    for i, name in enumerate(set_names):
        print(f"[{i+1}] {name}")
    
    while True:
        try:
            choice = int(input("Nhập số thứ tự Bộ đề: "))
            if 1 <= choice <= len(set_names):
                selected_set = set_names[choice - 1]
                break
            else:
                print("Lựa chọn không hợp lệ.")
        except ValueError:
            print("Vui lòng nhập một số.")

    # 2. Chọn Mã đề (Test ID)
    test_ids = list(key_data[selected_set].keys())
    print(f"\n--- CHỌN TEST TRONG {selected_set} ---")
    print(f"Các test có sẵn: {', '.join(test_ids)}")

    while True:
        selected_id = input(f"Nhập Test: ").strip()
        if selected_id in test_ids:
            break
        else:
            print(f"Test '{selected_id}' không tồn tại trong Bộ đề này.")

    # 3. Chọn Folder chứa bài làm
    print("\n--- NHẬP ĐƯỜNG DẪN THƯ MỤC ẢNH ---")
    while True:
        folder_path = input("Dán đường dẫn thư mục chứa ảnh bài làm: ").strip().replace('"', '') 
        if os.path.isdir(folder_path):
            break
        else:
            print("Đường dẫn không hợp lệ. Vui lòng thử lại.")
            
    return selected_set, selected_id, folder_path

def main():
    if os.name == 'nt':
        os.system('chcp 65001')

    print("=========================================")
    print("      TOEIC OMR SCORING APPLICATION      ")
    print("=========================================")
    
    try:
        config = load_config()
        all_keys_data = load_key(KEY_PATH)
        scoring_ref = load_scoring_ref(SCORING_REF_PATH)
        selected_set, selected_id, image_dir = get_user_selection(all_keys_data)
        key_raw = get_answer_key(all_keys_data, selected_set, selected_id)
        print(f"\n--- {selected_set}, test {selected_id} ---".upper())
        print(f"Working on: {Path(image_dir).name}")
        print("-----------------------------------------")
        
        warp_processor = WarpingProcessor(config)
        omr_engine = OMREngine(config)
        
        current_time = datetime.now().strftime("%Y-%m-%d")
        
        grade_manager = GradeManager(
            key_answer=key_raw, 
            scoring_ref=scoring_ref,
            set_name=selected_set, 
            test_id=selected_id,
            test_date=current_time
        )
        
        log_dir = Path.cwd().parent / "log"
        log_dir.mkdir(exist_ok=True)
        result_dir = log_dir / f"{current_time}_{selected_set}_{selected_id}".replace(" ", "").replace("-", "")
        result_dir.mkdir(parents=True, exist_ok=True)
        all_results_list = []
        
    except Exception as e:
        print(f"❌ LỖI KHỞI TẠO: {e}")
        return

    image_files = list(Path(image_dir).glob('*.jpg')) # Quét folder ảnh người dùng chọn
    if not image_files:
        print(f"Không tìm thấy file ảnh .jpg nào trong thư mục: {image_dir}.")
        return

    for img_path in image_files:
        base_name = img_path.stem
        print(f"\t⏳ Grading: {img_path.name}", end='\r')
        
        try:
            img_bgr = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_UNCHANGED)
            if img_bgr is None:
                raise RuntimeError("Không thể đọc/giải mã file ảnh.")

            img_warped_bgr, img_warped_binary = warp_processor.process_warping(img_bgr)
            
            answers_list, _, image_with_grid = omr_engine.process_omr(
                img_warped_binary, 
                img_warped_bgr
            )

            parts, _ = grade_manager.grade_answers(answers_list)

            grade_manager.save_result_image(base_name, image_with_grid, result_dir)
            row_dict = grade_manager.format_result(base_name, parts, answers_list)
            all_results_list.append(row_dict)
            
            print(f"\t✅ Graded: {img_path.name}")
            
        except Exception as e:
            print(f"\t❌ Error {img_path.name}: {e}")
            continue

    if all_results_list:
        save_results_to_excel(all_results_list, result_dir)

if __name__ == "__main__":
    main()