from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from datetime import datetime
from src.utils import app_logger, OMRUtils

class FormStateManager:
    """
    Quản lý trạng thái dữ liệu của Form.
    Nhiệm vụ:
    1. Lưu trữ các giá trị Input (Set, ID, Date, Files).
    2. Tự động cập nhật các giá trị dẫn xuất (Derived State) như Key đáp án.
    3. Validate dữ liệu trước khi cho phép chạy chấm điểm.
    """
    
    # Hằng số mặc định cho UI
    UNSELECTED_SET = "Select Set"
    UNSELECTED_ID = "Test"
    UNSELECTED_DATE_HINT = "Test Date (YYYY-MM-DD)"

    def __init__(self, all_keys_data: Dict[str, Dict[str, str]]):
        self.all_keys_data = all_keys_data
        
        self.state: Dict[str, Any] = {
            # User Inputs
            'set_name': self.UNSELECTED_SET,
            'test_id': self.UNSELECTED_ID,
            'test_date': self.UNSELECTED_DATE_HINT,
            'image_files': [], # List[Path]
            
            # Outputs
            'results': [],     # List[Dict]
            
            # Derived / Internal State
            'key': "",         # Chuỗi đáp án chuẩn
            'is_valid': False, 
            'error_message': None,
        }
        app_logger.debug("FormStateManager initialized.")
        
    def set_value(self, key: str, value: Any, skip_validation: bool = False):
        """Cập nhật giá trị state và kích hoạt tính toán lại nếu cần."""
        if key in self.state:
            old_value = self.state[key]
            self.state[key] = value
            
            # Chỉ log nếu giá trị thực sự thay đổi (tránh spam log)
            if old_value != value and key != 'results':
                app_logger.debug(f"State changed: {key} = {value}")

            if not skip_validation:
                self._update_derived_key()
            
    def get_value(self, key: str) -> Any:
        return self.state.get(key)
        
    def _update_derived_key(self):
        """
        Tự động tìm kiếm Answer Key khi người dùng chọn Set và Test ID.
        """
        set_name = self.state['set_name']
        test_id = self.state['test_id']
        new_key = ""
        
        # Chỉ tìm nếu đã chọn đủ thông tin
        if (set_name != self.UNSELECTED_SET and 
            test_id != self.UNSELECTED_ID and 
            set_name in self.all_keys_data):
            
            try:
                # Sử dụng Helper từ tầng Utils
                new_key = OMRUtils.get_answer_key(self.all_keys_data, set_name, test_id)
                app_logger.info(f"Answer Key found for {set_name} - {test_id}")
            except Exception:
                app_logger.warning(f"No key found for {set_name} - {test_id}")
                pass 
                
        self.state['key'] = new_key
        
    def validate_and_update_state(self) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra toàn vẹn dữ liệu trước khi bấm Start.
        """
        is_valid, error_msg = self._validate_form()
        self.state['is_valid'] = is_valid
        self.state['error_message'] = error_msg
        
        if not is_valid:
            app_logger.warning(f"Validation failed: {error_msg}")
        else:
            app_logger.info("Form validation passed. Ready to score.")
        
        return is_valid, error_msg

    def _validate_form(self) -> Tuple[bool, Optional[str]]:
        """Logic kiểm tra chi tiết."""
        
        # Đảm bảo Key mới nhất
        self._update_derived_key() 

        # 1. Kiểm tra Set Name
        if self.state['set_name'] == self.UNSELECTED_SET or not self.state['set_name']:
            return False, "Vui lòng chọn Bộ đề."
        
        # 2. Kiểm tra Test ID
        if self.state['test_id'] == self.UNSELECTED_ID or not self.state['test_id']:
            return False, "Vui lòng chọn Mã đề."

        # 3. Kiểm tra Answer Key
        if not self.state['key']:
             return False, "Lỗi dữ liệu: Không tìm thấy đáp án cho mã đề này."

        # 4. Kiểm tra Image Files
        if not self.state['image_files']:
            return False, "Vui lòng tải ít nhất một file ảnh bài làm."
             
        # 5. Kiểm tra Định dạng Ngày thi
        date_val = self.state['test_date']
        if date_val == self.UNSELECTED_DATE_HINT or not date_val.strip():
            # Nếu để trống, tự động lấy ngày hôm nay
            today_str = datetime.now().strftime('%Y-%m-%d')
            self.state['test_date'] = today_str
            app_logger.info(f"Auto-set date to today: {today_str}")
        else:
            try:
                datetime.strptime(date_val, '%Y-%m-%d')
            except ValueError:
                return False, "Ngày thi không đúng định dạng YYYY-MM-DD."

        return True, None