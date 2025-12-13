from typing import Tuple, List, Dict

class OMRUtils:
    """
    Class tĩnh chứa các thuật toán logic bổ trợ cho OMR (không phụ thuộc vào I/O).
    """

    @staticmethod
    def bits_to_char(bits: Tuple[int, ...], densities: List[float]) -> Tuple[str, Tuple[int, ...]]:
        """
        Chuyển đổi chuỗi bit (0,1,0,0) thành ký tự đáp án (B).
        
        Logic xử lý:
        1. Không tô -> '0'
        2. Tô 1 ô -> Mapping trực tiếp (A,B,C,D)
        3. Tô nhiều ô -> Chọn ô có density lớn nhất (đậm nhất).
        
        Args:
            bits: Tuple 4 phần tử (0 hoặc 1). VD: (1, 0, 1, 0)
            densities: List 4 phần tử float tương ứng độ đậm.
            
        Returns:
            Tuple[str, Tuple]: Ký tự đáp án và bộ bit đã được chuẩn hóa (chỉ giữ lại 1 bit 1).
        """
        # Validate input basic
        if len(bits) != 4 or len(densities) != 4:
            return '0', (0, 0, 0, 0)

        sum_bits = sum(bits)
        final_bits = list(bits)

        # Case 1: Không tô gì cả
        if sum_bits == 0:
            return '0', (0, 0, 0, 0)

        # Case 2: Tô nhiều hơn 1 ô -> Chọn ô đậm nhất (Logic thông minh)
        if sum_bits > 1:
            # Tạo list các cặp (density, index) cho các vị trí được tô
            candidates = [(densities[i], i) for i, val in enumerate(bits) if val == 1]
            
            if not candidates: # Phòng trường hợp lỗi lạ
                return '0', (0, 0, 0, 0)
                
            # Tìm index có density lớn nhất
            best_idx = max(candidates, key=lambda item: item[0])[1]
            
            # Reset lại bit: Chỉ giữ lại bit đậm nhất là 1, còn lại về 0
            final_bits = [0] * 4
            final_bits[best_idx] = 1

        final_bits_tuple = tuple(final_bits)

        # Case 3: Mapping bit sang ký tự
        mapping = {
            (1, 0, 0, 0): 'A',
            (0, 1, 0, 0): 'B',
            (0, 0, 1, 0): 'C',
            (0, 0, 0, 1): 'D'
        }
        
        return mapping.get(final_bits_tuple, '0'), final_bits_tuple

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