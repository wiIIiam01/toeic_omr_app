from typing import Tuple, Dict, Any, List
from pathlib import Path
import json
import pandas as pd

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
    
def save_results_to_excel(results: List[Dict[str, Any]], result_dir: Path):
    
    if not results:
        return # Không có gì để lưu
    
    df_new = pd.DataFrame(results)
    
    # Tên file được tạo từ set_name và test_id
    excel_path = result_dir / f"{result_dir.name}_summary.xlsx"
    
    if excel_path.exists():
        # Nếu file đã tồn tại, đọc file cũ và nối dữ liệu (append)
        try:
            df_old = pd.read_excel(excel_path)
            # Đảm bảo cột Timestamp là chuỗi trước khi nối để tránh lỗi format
            df_old['Date'] = df_old['Date'].astype(str)
            df_new['Date'] = df_new['Date'].astype(str)
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            
        except Exception as e:
            # Nếu có lỗi khi đọc, coi như df_combined là df_new (ghi đè file cũ)
            print(f"Lỗi khi đọc file Excel cũ, sẽ ghi đè: {e}")
            df_combined = df_new
    else:
        df_combined = df_new

    try:
        # Đảm bảo thư mục cha tồn tại (dù đã được tạo ở bước chấm điểm)
        result_dir.mkdir(parents=True, exist_ok=True) 
        df_combined.to_excel(excel_path, index=False)
        print(f"Results saved at: {result_dir}")
        
        # Trả về đường dẫn file đã lưu để hiển thị thông báo
        return excel_path 
        
    except Exception as e:
        print(f"Error when saving results: {e}")
        # Ném lỗi lại để lớp GUI có thể bắt và hiển thị
        raise e