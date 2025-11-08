from typing import Tuple, Dict, Any, List
from pathlib import Path
import json
import os

def load_config(filename: Path = Path("config.json")) -> Dict[str, Any]:
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Lỗi: Không tìm thấy file cấu hình {filename}. Vui lòng tạo file này.")

def bits_to_char(bits: Tuple[int, int, int, int], densities: List[float]) -> Tuple[str, Tuple[int, int, int, int]]:
    sum_bits = sum(bits)
    bits_list = list(bits)
    
    if sum_bits == 0: 
        return '0', (0, 0, 0, 0)
    
    if sum_bits > 1:
        marked_info = [(densities[i], i) for i, bit in enumerate(bits) if bit == 1]
        best_index = max(marked_info, key=lambda x: x[0])[1]
        bits_list = [0] * 4
        bits_list[best_index] = 1
     
    final_bits = tuple(bits_list)
    
    if final_bits == (1,0,0,0): return 'A', final_bits
    if final_bits == (0,1,0,0): return 'B', final_bits
    if final_bits == (0,0,1,0): return 'C', final_bits
    if final_bits == (0,0,0,1): return 'D', final_bits

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
    
def load_key(key_file_path: str = 'key.json') -> Dict[str, Dict[str, str]]:
    try:
        with open(key_file_path, 'r', encoding='utf-8') as f:
            key_data = json.load(f)
        if not isinstance(key_data, dict):
            raise ValueError("Cấu trúc file key.json không hợp lệ.")           
        return key_data
        
    except json.JSONDecodeError:
        raise ValueError(f"Lỗi: Không thể giải mã file JSON tại {key_file_path}. Kiểm tra lỗi cú pháp JSON.")
    except Exception as e:
        raise Exception(f"Lỗi khi tải key.json: {e}")
    
def get_user_selection(key_data: Dict[str, Dict[str, str]]) -> Tuple[str, str, str]:
    set_names = list(key_data.keys())
    print("\n--- CHỌN BỘ ĐỀ ---")
    for i, name in enumerate(set_names):
        print(f"[{i+1}] {name}")
    
    while True:
        try:
            choice = int(input("Nhập số thứ tự Bộ đề: "))
            if 1 <= choice <= len(set_names):
                selected_set = set_names[choice - 1]
                break
            else:
                print("Lựa chọn không hợp lệ.")
        except ValueError:
            print("Vui lòng nhập một số.")

    # 2. Chọn Mã đề (Test ID)
    test_ids = list(key_data[selected_set].keys())
    print(f"\n--- CHỌN TEST TRONG {selected_set} ---")
    print(f"Các test có sẵn: {', '.join(test_ids)}")

    while True:
        selected_id = input(f"Nhập Test: ").strip()
        if selected_id in test_ids:
            break
        else:
            print(f"Test '{selected_id}' không tồn tại trong Bộ đề này.")

    # 3. Chọn Folder chứa bài làm
    print("\n--- NHẬP ĐƯỜNG DẪN THƯ MỤC ẢNH ---")
    while True:
        # .replace('"', '') để loại bỏ dấu ngoặc kép khi dán đường dẫn trên Windows
        folder_path = input("Dán đường dẫn thư mục chứa ảnh bài làm: ").strip().replace('"', '') 
        if os.path.isdir(folder_path):
            break
        else:
            print("Đường dẫn không hợp lệ. Vui lòng thử lại.")
            
    return selected_set, selected_id, folder_path

def get_answer_key(key_data: Dict[str, Dict[str, str]], set_name: str, test_id: str) -> str:
    if set_name not in key_data:
        raise KeyError(f"Lỗi: Không tìm thấy Bộ đề '{set_name}' trong key.json.")
    
    if test_id not in key_data[set_name]:
        raise KeyError(f"Lỗi: Không tìm thấy Mã đề '{test_id}' trong Bộ đề '{set_name}'.")
        
    return key_data[set_name][test_id]

def load_scoring_ref(ref_file_path: str = 'scoring_ref.json') -> Dict[str, Dict[str, int]]:
    try:
        with open(ref_file_path, 'r', encoding='utf-8') as f:
            ref_data = json.load(f)
            
            for key in ref_data:
                ref_data[key] = {int(k): v for k, v in ref_data[key].items()}
            
            return ref_data
            
    except json.JSONDecodeError:
        raise ValueError(f"Lỗi: Không thể giải mã file JSON tại {ref_file_path}.")
    except Exception as e:
        raise Exception(f"Lỗi khi tải scoring_ref.json: {e}")