import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from processing.utils import load_config
from processing.warp import WarpingProcessor
from processing.omr_engine import OMREngine
from processing.grade import GradeManager

def _load_key_from_file(key_path: Path) -> str:
    try:
        with key_path.open("r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Lỗi: Không tìm thấy file key {key_path}. Vui lòng tạo file này.")

def main():
    try:
        config = load_config()
        key_path = Path("key.txt")
        
        key_raw = _load_key_from_file(key_path) 
        
        warp_processor = WarpingProcessor(config)
        omr_engine = OMREngine(config)
        
        grade_manager = GradeManager(key_answer=key_raw) 
        
        result_dir = Path("Result")
        result_xlsx = Path("result.xlsx")
        all_results_list = []
        
    except Exception as e:
        print(f"❌ LỖI KHỞI TẠO: {e}")
        return

    image_files = list(Path('.').glob('*.jpg'))
    if not image_files:
        print("Không tìm thấy file ảnh .jpg nào trong thư mục hiện tại.")
        return

    for img_path in image_files:
        base_name = img_path.stem
        print(f"Bắt đầu xử lý: {img_path.name}")
        
        try:
            img_bgr = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_UNCHANGED)
            if img_bgr is None:
                raise RuntimeError("Không thể đọc/giải mã file ảnh.")

            img_warped_bgr, img_warped_binary, img_warped_gray = warp_processor.process_warping(img_bgr)
            
            answers_list, result_matrix, image_with_grid = omr_engine.process_omr(
                img_warped_binary, 
                img_warped_bgr
            )

            parts, _ = grade_manager.grade_answers(answers_list)

            grade_manager.save_result_image(base_name, image_with_grid, result_dir)
            row_dict = grade_manager.format_result(base_name, parts, answers_list)
            all_results_list.append(row_dict)
            
            print(f"✅ Xử lý thành công: {img_path.name}.")
            
        except Exception as e:
            print(f"❌ LỖI khi xử lý file {img_path.name}: {e}")
            continue

    if all_results_list:
        grade_manager.save_all_to_excel(all_results_list, result_xlsx)
        print(f"\n✨ Đã lưu tất cả kết quả vào {result_xlsx}.")

if __name__ == "__main__":
    main()