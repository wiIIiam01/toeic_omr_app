"""
Package Core: Chứa logic nghiệp vụ cốt lõi của ứng dụng OMR.
Bao gồm:
- WarpingProcessor: Xử lý hình học ảnh.
- OMREngine: Nhận diện đáp án.
- GradeManager: Chấm điểm và xử lý kết quả.
"""

from .warp_processor import WarpingProcessor
from .omr_engine import OMREngine
from .grade_manager import GradeManager

__all__ = ['WarpingProcessor', 'OMREngine', 'GradeManager']