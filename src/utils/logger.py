import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(name: str = "TOEIC_OMR", log_dir: str = "logs") -> logging.Logger:
    """
    Thiết lập Logger tập trung cho toàn bộ ứng dụng.
    
    Cơ chế hoạt động:
    1. Ghi ra File: Mức DEBUG (Ghi lại mọi chi tiết để lập trình viên sửa lỗi).
    2. Ghi ra Console: Mức INFO (Thông tin gọn gàng cho người dùng xem).
    """
    # 1. Chuẩn bị thư mục Log
    # Lấy đường dẫn gốc của dự án (thư mục chứa src)
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent.parent
    
    # Tạo thư mục logs nằm ngang hàng với src
    log_path = project_root / log_dir
    log_path.mkdir(parents=True, exist_ok=True)

    # 2. Tạo tên file log theo ngày (VD: session_2023-10-25.log)
    log_filename = f"session_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_path = log_path / log_filename

    # 3. Khởi tạo Logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG) # Bắt tất cả các log từ mức thấp nhất

    # Ngăn việc tạo duplicate logs nếu hàm này được gọi nhiều lần
    if logger.hasHandlers():
        return logger

    # 4. Định dạng Log
    # Format: [Giờ:Phút:Giây] - [MỨC ĐỘ] - Nội dung thông báo
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%H:%M:%S')

    # --- HANDLER 1: Ghi vào File ---
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG) # Ghi tất cả lỗi, warning, info, debug
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # --- HANDLER 2: Ghi ra màn hình Console ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Chỉ ghi Info, Warning, Error (bỏ qua debug rác)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# Khởi tạo singleton logger để các file khác import và dùng ngay
app_logger = setup_logger()