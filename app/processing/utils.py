from typing import Tuple, Dict, Any
from pathlib import Path
import json

def load_config(filename: Path = Path("config.json")) -> Dict[str, Any]:
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Lỗi: Không tìm thấy file cấu hình {filename}. Vui lòng tạo file này.")

def bits_to_char(bits: Tuple[int, int, int, int]) -> str:
    """Chuyển 4 bit nhị phân (0, 1) thành ký tự đáp án (0, A, B, C, D, X)."""
    if bits == (0,0,0,0): return '0' # Không tô
    if bits == (1,0,0,0): return 'A'
    if bits == (0,1,0,0): return 'B'
    if bits == (0,0,1,0): return 'C'
    if bits == (0,0,0,1): return 'D'
    return 'X' # Tô quá 1 ô (hoặc lỗi khác)

def get_answer_parts_ranges():
    """Trả về các phạm vi câu hỏi cho việc chấm điểm từng phần."""
    # (start_1_based, end_1_based)
    return [
        (1, 6),
        (7, 31),
        (32, 70),
        (71, 100),
        (101, 130),
        (131, 146),
        (147, 200)
    ]