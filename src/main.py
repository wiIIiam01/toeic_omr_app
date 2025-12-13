"""
Entry Point của ứng dụng TOEIC OMR.
Chịu trách nhiệm thiết lập môi trường và khởi chạy giao diện chính.
"""

import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# --- THIẾT LẬP ĐƯỜNG DẪN IMPORT ---
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import từ các package đã tái cấu trúc
from src.utils import app_logger
from src.ui import OMRApplication

def setup_exception_handling(root):
    """
    Bắt các lỗi không được xử lý (Uncaught Exceptions) trong Tkinter
    và hiển thị thông báo lỗi thay vì crash ứng dụng im lặng.
    """
    # SỬA LỖI: Xóa tham số 'self' ở đây vì hàm này không nằm trong class nào cả
    def report_callback_exception(exc, val, tb):
        app_logger.critical(f"Uncaught Exception: {val}", exc_info=(exc, val, tb))
        messagebox.showerror("Critical Error", f"Đã xảy ra lỗi nghiêm trọng:\n{val}\n\nVui lòng kiểm tra log để biết thêm chi tiết.")
        
    root.report_callback_exception = report_callback_exception

def main():
    """Hàm khởi chạy chính."""
    app_logger.info("==========================================")
    app_logger.info("   STARTING TOEIC OMR SCORING APP v2.0    ")
    app_logger.info("==========================================")
    
    # 1. Khởi tạo Root Tkinter
    try:
        root = tk.Tk()
    except Exception as e:
        app_logger.critical(f"Failed to initialize Tkinter: {e}")
        return

    # 2. Thiết lập cơ chế bắt lỗi toàn cục
    setup_exception_handling(root)

    # 3. Khởi tạo App Controller
    try:
        app = OMRApplication(root)
        
        # Xử lý sự kiện tắt cửa sổ an toàn
        def on_closing():
            if messagebox.askokcancel("Thoát", "Bạn có chắc chắn muốn thoát chương trình?"):
                app_logger.info("Application closed by user.")
                root.destroy()
                
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        app_logger.info("UI initialized successfully. Entering main loop.")
        root.mainloop()
        
    except Exception as e:
        app_logger.critical(f"Fatal Error during app startup: {e}", exc_info=True)
        messagebox.showerror("Startup Error", f"Không thể khởi động ứng dụng:\n{e}")
    finally:
        app_logger.info("Application Process Terminated.")

if __name__ == "__main__":
    main()