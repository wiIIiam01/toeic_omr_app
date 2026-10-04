from threading import Thread
from typing import List, TYPE_CHECKING, Optional, Dict, Any
from pathlib import Path
import cv2
import numpy as np
import time
import os
from concurrent.futures import ThreadPoolExecutor

# Import từ các package đã được tái cấu trúc
from src.core import WarpingProcessor, OMREngine, GradeManager
from src.utils import app_logger

# Xử lý circular import cho type hinting với lớp GUI chính
if TYPE_CHECKING:
    from src.ui.app_window import OMRApplication

class ScoringWorker(Thread):
    """
    Worker Thread chạy ngầm để xử lý chấm điểm danh sách ảnh.
    Giúp giao diện không bị treo (freeze) khi xử lý các thuật toán nặng của OpenCV.
    """

    def __init__(self, 
                 gui_app: 'OMRApplication', 
                 image_files: List[Path], 
                 warp_processor: WarpingProcessor, 
                 omr_engine: OMREngine, 
                 grade_manager: GradeManager,
                 answer_key: str, 
                 result_dir: Path):
        
        super().__init__()
        self.gui_app = gui_app
        self.image_files = image_files
        self.warp_processor = warp_processor
        self.omr_engine = omr_engine
        self.grade_manager = grade_manager
        self.answer_key = answer_key
        self.result_dir = result_dir
        
        # Đặt thread là daemon để nó tự động tắt khi chương trình chính tắt
        self.daemon = True 

    def _process_one(self, item):
        """Chấm 1 ảnh. Không đụng tới UI; trả về (img_path, result_dict, error_msg)."""
        index, img_path = item
        base_name = img_path.stem
        try:
            t0 = time.perf_counter()
            app_logger.debug(f"[{index+1}/{len(self.image_files)}] Processing: {img_path.name}")

            stream = np.fromfile(str(img_path), np.uint8)
            img_bgr = cv2.imdecode(stream, cv2.IMREAD_UNCHANGED)
            if img_bgr is None:
                raise ValueError("Không thể đọc file ảnh (File lỗi hoặc định dạng không hỗ trợ).")

            warped_bgr, warped_bin, warped_marker, ho_lot, ten = self.warp_processor.process_warping(img_bgr)
            answers_list, image_with_grid, conf_stats = self.omr_engine.process_omr(
                self.answer_key, warped_marker, warped_bin, warped_bgr
            )
            parts_stats = self.grade_manager.grade_answers(answers_list)
            self.grade_manager.save_result_image(base_name, image_with_grid, self.result_dir)

            result = self.grade_manager.format_result(
                ho_lot, ten, base_name, parts_stats, answers_list, conf_stats
            )
            return img_path, result, None
        except Exception as e:
            app_logger.error(f"Error processing {img_path.name}: {e}")
            return img_path, None, str(e)

    def run(self):
        total_files = len(self.image_files)
        workers = max(1, min(4, os.cpu_count() or 2, total_files))  # cap 4: mỗi ảnh full-res ngốn ~100-150MB RAM
        app_logger.info(f"Worker started. Processing {total_files} files with {workers} threads...")

        start_time = time.time()
        success_count = 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            # map() trả kết quả theo đúng thứ tự file -> bảng UI và CSV giữ nguyên thứ tự
            for img_path, result_dict, error_msg in pool.map(
                    self._process_one, enumerate(self.image_files)):
                if result_dict is not None:
                    success_count += 1
                self.gui_app.master.after(0, self.gui_app.on_file_graded,
                                          img_path, result_dict, error_msg)

        elapsed = time.time() - start_time
        app_logger.info(f"Worker finished. Success: {success_count}/{total_files}. Time: {elapsed:.2f}s")
        self.gui_app.master.after(0, self.gui_app.on_scoring_complete)
