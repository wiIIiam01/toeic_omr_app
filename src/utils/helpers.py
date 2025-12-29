from typing import Tuple, List, Dict

class OMRUtils:
    """
    Class tĩnh chứa các thuật toán logic bổ trợ (không phụ thuộc vào I/O).
    """
    @staticmethod
    def get_answer_parts_ranges() -> List[Tuple[int, int]]:
        """
        Trả về danh sách range câu hỏi cho 7 phần thi TOEIC (1-based index).
        Dùng để chia điểm.
        """
        return [
            (1, 6),     # Part 1: Photographs
            (7, 31),    # Part 2: Question-Response
            (32, 70),   # Part 3: Conversations
            (71, 100),  # Part 4: Talks
            (101, 130), # Part 5: Incomplete Sentences
            (131, 146), # Part 6: Text Completion
            (147, 200)  # Part 7: Reading Comprehension
        ]

    @staticmethod
    def get_answer_key(key_data: Dict[str, Dict[str, str]], set_name: str, test_id: str) -> str:
        """
        Helper để lấy chuỗi đáp án từ Dict dữ liệu key.
        """
        if set_name not in key_data:
            raise KeyError(f"Không tìm thấy Bộ đề: '{set_name}'")

        if test_id not in key_data[set_name]:
            raise KeyError(f"Không tìm thấy Mã đề: '{test_id}' trong bộ '{set_name}'")

        return key_data[set_name][test_id]