import cv2
import os
import numpy as np
import pandas as pd
from pathlib import Path
from processing.utils import load_config, load_key, get_user_selection, get_answer_key, load_scoring_ref
from processing.warp import WarpingProcessor
from processing.omr_engine import OMREngine
from processing.grade import GradeManager

KEY_PATH = Path("key.json")
SCORING_REF_PATH = 'scoring_ref.json'

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
        print(f"\n✅ Đã chọn Bộ đề: **{selected_set}**, Mã đề: **{selected_id}**. ({len(key_raw)} câu)")
        print(f"Bắt đầu chấm điểm thư mục: {image_dir}")
        
        warp_processor = WarpingProcessor(config)
        omr_engine = OMREngine(config)
        
        grade_manager = GradeManager(
            key_answer=key_raw, 
            scoring_ref=scoring_ref,
            set_name=selected_set, 
            test_id=selected_id
        )
        
        base_dir = Path(image_dir).parent
        folder_name = Path(image_dir).name
        result_dir = base_dir / f"{folder_name}_GRADED"
        result_dir.mkdir(parents=True, exist_ok=True)
        
        result_xlsx = result_dir / "result_summary.xlsx"
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
        print(f"\tĐang xử lý: {img_path.name}", end='\r')
        
        try:
            img_bgr = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_UNCHANGED)
            if img_bgr is None:
                raise RuntimeError("Không thể đọc/giải mã file ảnh.")

            img_warped_bgr, img_warped_binary, _ = warp_processor.process_warping(img_bgr)
            
            answers_list, _, image_with_grid = omr_engine.process_omr(
                img_warped_binary, 
                img_warped_bgr
            )

            parts, _ = grade_manager.grade_answers(answers_list)

            grade_manager.save_result_image(base_name, image_with_grid, result_dir)
            row_dict = grade_manager.format_result(base_name, parts, answers_list)
            all_results_list.append(row_dict)
            
            print(f"\t✅ Xử lý thành công: {img_path.name}.")
            
        except Exception as e:
            print(f"\t❌ LỖI khi xử lý file {img_path.name}: {e}")
            continue

    if all_results_list:
        grade_manager.save_all_to_excel(all_results_list, result_xlsx)
        print(f"\n✨ Đã lưu tất cả kết quả vào {result_xlsx}.")
        print(f"Kết quả ảnh và Excel được lưu tại: **{result_dir}**")

if __name__ == "__main__":
    main()