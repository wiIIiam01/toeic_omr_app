from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from processing.utils import get_answer_key

class FormStateManager:
    """Quản lý và cập nhật trạng thái của các Input/Điều kiện cần thiết cho quá trình chấm điểm OMR."""
    
    # Biến hằng số mặc định cho UI
    UNSELECTED_SET = "Select Set"
    UNSELECTED_ID = "Test"
    UNSELECTED_DATE_HINT = "Test Date (YYYY-MM-DD)"

    def __init__(self, all_keys_data: Dict[str, Dict[str, str]]):
        self.all_keys_data = all_keys_data
        
        # 1. TRẠNG THÁI FORM CHÍNH
        self.state: Dict[str, Any] = {
            # INPUTS CẦN TỪ NGƯỜI DÙNG
            'set_name': self.UNSELECTED_SET,
            'test_id': self.UNSELECTED_ID,
            'test_date': self.UNSELECTED_DATE_HINT,
            # image_files: HÀNG ĐỢI (QUEUE) - List[Path] chứa đường dẫn file ảnh
            'image_files': [], 
            # results: Danh sách lưu trữ kết quả chấm điểm (từng file ảnh)
            # Dạng: List[Dict[str, Any]]
            'results': [],
            
            # DERIVED STATE (Trạng thái dẫn xuất)
            'key': "", # Chuỗi đáp án chuẩn
            'is_valid': False, # Trạng thái Form hợp lệ để chạy Scoring
            'error_message': None, # Thông báo lỗi gần nhất
        }
        
    def set_value(self, key: str, value: Any, skip_validation: bool = False):
        """Cập nhật một giá trị trong trạng thái. Thường được gọi khi input thay đổi."""
        if key in self.state:
            self.state[key] = value
            if not skip_validation:
                self._update_derived_key()
            
    def get_value(self, key: str) -> Any:
        """Lấy một giá trị từ trạng thái."""
        return self.state.get(key)
        
    def _update_derived_key(self):
        """Chỉ cập nhật Answer Key khi Set Name hoặc Test ID thay đổi."""
        set_name = self.state['set_name']
        test_id = self.state['test_id']
        new_key = ""
        
        if set_name in self.all_keys_data and test_id in self.all_keys_data.get(set_name, {}):
            try:
                new_key = get_answer_key(self.all_keys_data, set_name, test_id)
            except Exception:
                pass 
                
        self.state['key'] = new_key
        
    def validate_and_update_state(self):
        """Thực hiện kiểm tra toàn bộ Form. Chỉ gọi khi bấm START."""
        is_valid, error_msg = self._validate_form()
        self.state['is_valid'] = is_valid
        self.state['error_message'] = error_msg
        
        # In ra trạng thái để debug
        print(f"\n--- VALIDATION ON START CLICKED ---")
        print(f"Set: {self.state['set_name']} | ID: {self.state['test_id']} | Valid: {is_valid}")
        print(f"Key Length: {len(self.state['key']) if self.state['key'] else 0} | Files: {len(self.state['image_files'])}")
        if not is_valid:
            print(f"Error: {error_msg}")
        print(f"-----------------------------------")
        
        return is_valid, error_msg

        
    def _validate_form(self) -> Tuple[bool, Optional[str]]:
        """Kiểm tra tất cả ràng buộc cần thiết để chạy OMR Scoring."""
        
        # Đảm bảo Key được cập nhật trước khi validation
        self._update_derived_key() 

        # 1. Kiểm tra Set Name
        if self.state['set_name'] == self.UNSELECTED_SET or not self.state['set_name']:
            return False, "Vui lòng chọn Bộ đề."
        
        # 2. Kiểm tra Test ID
        if self.state['test_id'] == self.UNSELECTED_ID or not self.state['test_id']:
            return False, "Vui lòng chọn Test."

        # 3. Kiểm tra Answer Key
        if not self.state['key']:
             return False, "Lỗi: Không tìm thấy đáp án."

        # 4. Kiểm tra Image Files
        if not self.state['image_files']:
            return False, "Vui lòng tải ít nhất một file ảnh bài làm."
             
        # 5. Kiểm tra Định dạng Ngày thi (YYYY-MM-DD)
        try:
            if self.state['test_date'] != self.UNSELECTED_DATE_HINT:
                datetime.strptime(self.state['test_date'], '%Y-%m-%d')
            else:
                self.state['test_date'] = datetime.now().strftime('%Y-%m-%d')
        except ValueError:
            return False, "Ngày thi không đúng định dạng YYYY-MM-DD."

        return True, None