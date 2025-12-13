from threading import Thread
from typing import List, TYPE_CHECKING, Optional, Dict, Any
from pathlib import Path
import cv2
import numpy as np
import time

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
                 result_dir: Path):
        
        super().__init__()
        self.gui_app = gui_app
        self.image_files = image_files
        self.warp_processor = warp_processor
        self.omr_engine = omr_engine
        self.grade_manager = grade_manager
        self.result_dir = result_dir
        
        # Đặt thread là daemon để nó tự động tắt khi chương trình chính tắt
        self.daemon = True 

    def run(self):
        """
        Hàm chính thực thi khi thread bắt đầu (.start()).
        Chạy quá trình chấm điểm tuần tự cho từng file.
        """
        total_files = len(self.image_files)
        app_logger.info(f"Worker started. Processing {total_files} files...")
        
        start_time = time.time()
        success_count = 0
        
        for index, img_path in enumerate(self.image_files):
            result_dict = None
            error_msg = None
            base_name = img_path.stem
            
            try:
                app_logger.debug(f"[{index+1}/{total_files}] Processing: {img_path.name}")
                
                # 1. Đọc ảnh (Hỗ trợ đường dẫn Unicode/Tiếng Việt)
                # cv2.imread không hỗ trợ tốt đường dẫn tiếng Việt trên Windows, 
                # nên dùng np.fromfile -> cv2.imdecode
                stream = np.fromfile(str(img_path), np.uint8)
                img_bgr = cv2.imdecode(stream, cv2.IMREAD_UNCHANGED)
                
                if img_bgr is None:
                    raise ValueError("Không thể đọc file ảnh (File lỗi hoặc định dạng không hỗ trợ).")

                # 2. Xử lý Warping (Căn chỉnh)
                img_warped_bgr, img_warped_binary, img_warped_marker = self.warp_processor.process_warping(img_bgr)
                
                # 3. Xử lý OMR (Quét đáp án)
                answers_list, _, image_with_grid = self.omr_engine.process_omr(
                    img_warped_marker,
                    img_warped_binary, 
                    img_warped_bgr
                )

                # 4. Chấm điểm
                parts_stats, _ = self.grade_manager.grade_answers(answers_list)

                # 5. Lưu ảnh kết quả & Format dữ liệu
                # Lưu ảnh có vẽ lưới chấm điểm để đối chiếu
                self.grade_manager.save_result_image(base_name, image_with_grid, self.result_dir)
                
                # Tạo dict kết quả để hiển thị lên bảng
                result_dict = self.grade_manager.format_result(base_name, parts_stats, answers_list)
                
                success_count += 1
            
            except Exception as e:
                error_msg = str(e)
                app_logger.error(f"Error processing {img_path.name}: {error_msg}")
            
            # Cập nhật giao diện (Thread-safe Call)
            # Chúng ta KHÔNG được gọi trực tiếp update UI từ đây, mà phải dùng after() hoặc queue.
            # Ở đây ta dùng after(0, callback, args...) của Tkinter widget.
            self.gui_app.master.after(0, self.gui_app.on_file_graded, img_path, result_dict, error_msg)

        elapsed_time = time.time() - start_time
        app_logger.info(f"Worker finished. Success: {success_count}/{total_files}. Time: {elapsed_time:.2f}s")
        
        # Thông báo hoàn tất quy trình
        self.gui_app.master.after(0, self.gui_app.on_scoring_complete)