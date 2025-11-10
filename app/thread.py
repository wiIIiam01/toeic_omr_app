from threading import Thread
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path
import cv2
import numpy as np
from processing.warp import WarpingProcessor
from processing.omr_engine import OMREngine
from processing.grade import GradeManager

# Xử lý circular import cho type hinting với lớp GUI chính
if TYPE_CHECKING:
    from gui import OMRLayoutDesign

class ScoringThread(Thread):
    """
    Luồng chạy ngầm để thực hiện quá trình chấm điểm ảnh (OMR, Warping, Grading)
    tránh làm đơ giao diện người dùng chính (GUI).
    """

    def __init__(self, app_gui: 'OMRLayoutDesign', image_files: List[Path], 
                 warp_processor: WarpingProcessor, omr_engine: OMREngine, 
                 grade_manager: GradeManager, result_dir: Path):
        
        super().__init__()
        self.app_gui = app_gui
        self.image_files = image_files
        self.warp_processor = warp_processor
        self.omr_engine = omr_engine
        self.grade_manager = grade_manager
        self.result_dir = result_dir

    def run(self):
        """Chạy quá trình chấm điểm cho từng file ảnh."""
        
        for img_path in self.image_files:
            result_dict = None
            error_msg = None
            base_name = img_path.stem
            
            try:
                # 1. Đọc ảnh (dùng imdecode để hỗ trợ đường dẫn tiếng Việt)
                img_bgr = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_UNCHANGED)
                if img_bgr is None:
                    raise RuntimeError("Không thể đọc/giải mã file ảnh.")

                # 2. Xử lý Warping
                img_warped_bgr, img_warped_binary = self.warp_processor.process_warping(img_bgr)
                
                # 3. Xử lý OMR (Quét đáp án)
                answers_list, _, image_with_grid = self.omr_engine.process_omr(
                    img_warped_binary, 
                    img_warped_bgr
                )

                # 4. Chấm điểm
                parts, _ = self.grade_manager.grade_answers(answers_list)

                # 5. Lưu kết quả ảnh & Định dạng kết quả
                self.grade_manager.save_result_image(base_name, image_with_grid, self.result_dir)
                result_dict = self.grade_manager.format_result(base_name, parts, answers_list)
            
            except Exception as e:
                error_msg = str(e)
                print(f"Lỗi khi chấm điểm {img_path.name}: {error_msg}")
            
            # Cập nhật giao diện người dùng thông qua callback (chạy trên luồng chính)
            self.app_gui.master.after(0, self.app_gui.on_file_graded, img_path, result_dict, error_msg)

        # Thông báo hoàn tất
        self.app_gui.master.after(0, self.app_gui.on_scoring_complete)