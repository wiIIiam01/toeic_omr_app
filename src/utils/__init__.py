"""
Package Utils: Chứa các công cụ hỗ trợ dùng chung cho toàn bộ dự án.
Bao gồm: Logging, File I/O (JSON/Excel), và các hàm toán học bổ trợ OMR.
"""

# Import các thành phần chính để expose ra ngoài package
from .logger import app_logger
from .file_io import FileHandler
from .helpers import OMRUtils

# Định nghĩa những gì sẽ được export khi dùng "from src.utils import *"
__all__ = ['app_logger', 'FileHandler', 'OMRUtils']