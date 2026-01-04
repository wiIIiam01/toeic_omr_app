import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from .logger import app_logger

class FileHandler:
    """
    Class tĩnh (Static Class) chuyên trách các tác vụ Input/Output (Đọc/Ghi file).
    Mục tiêu: Đảm bảo tính nhất quán trong việc xử lý file và bắt lỗi tập trung.
    """

    @staticmethod
    def load_json(file_path: Path) -> Dict[str, Any]:
        """
        Tải dữ liệu từ file JSON an toàn.
        
        Args:
            file_path (Path): Đường dẫn đến file.
            
        Returns:
            Dict: Dữ liệu JSON đã parse.
        """
        # Type enforcement
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        try:
            # Resolve path để đảm bảo đường dẫn tuyệt đối
            resolved_path = file_path.resolve()
            
            if not resolved_path.exists():
                app_logger.error(f"File not found: {resolved_path}")
                raise FileNotFoundError(f"Không tìm thấy file: {resolved_path}")

            with open(resolved_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            app_logger.debug(f"Loaded JSON successfully: {resolved_path.name}")
            return data

        except json.JSONDecodeError as e:
            app_logger.critical(f"JSON Syntax Error in {file_path}: {e}")
            raise ValueError(f"Lỗi cú pháp JSON trong file {file_path.name}")
        except Exception as e:
            app_logger.error(f"Unexpected error loading {file_path}: {e}")
            raise

    @staticmethod
    def load_config(filename: Path = Path("config.json")) -> Dict[str, Any]:
        """Wrapper để tải file cấu hình app."""
        return FileHandler.load_json(filename)

    @staticmethod
    def load_key(key_file_path: Path) -> Dict[str, Dict[str, str]]:
        """Wrapper để tải file đáp án."""
        return FileHandler.load_json(key_file_path)

    @staticmethod
    def load_scoring_ref(ref_file_path: Path) -> Dict[str, Dict[int, int]]:
        """
        Wrapper để tải bảng điểm.
        Cần xử lý chuyển đổi key từ string sang int (vì JSON lưu key là string).
        """
        try:
            data = FileHandler.load_json(ref_file_path)
            # Logic xử lý đặc thù của scoring_ref: Key "Số câu đúng" phải là Int
            processed_data = {}
            for scale_type, scale_dict in data.items():
                processed_data[scale_type] = {int(k): v for k, v in scale_dict.items()}
            return processed_data
        except Exception as e:
            app_logger.error(f"Error processing scoring ref: {e}")
            raise

    @staticmethod
    def save_results(results: List[Dict[str, Any]]) -> Optional[Path]:
        """
        Lưu kết quả ra CSV. Sử dụng mode 'a' để tối ưu hiệu suất.
        """
        if not results:
            app_logger.warning("Không có kết quả để lưu.")
            return None

        try:
            master_dir = Path("data")
            master_dir.mkdir(exist_ok=True)
            master_path = master_dir / "master.csv"

            df_new = pd.DataFrame(results)
            
            EXCLUDED_FIELDS = ['Reference', 'Confidence', 'LowestConf', 'LowestConfidence']
            cols_to_drop = [col for col in EXCLUDED_FIELDS if col in df_new.columns]
            if cols_to_drop:
                df_new.drop(columns=cols_to_drop, inplace=True)
            
            # Đảm bảo cột Date luôn là string để thống nhất dữ liệu
            if 'Date' in df_new.columns:
                df_new['Date'] = df_new['Date'].astype(str)

            if master_path.exists():
                df_old = pd.read_csv(master_path)                
                df_final = pd.concat([df_old, df_new], ignore_index=True)
                
                # KEY LOGIC: Lọc trùng. 
                subset_keys = ['Date', 'Class', 'Name', 'Set', 'Test']
                valid_keys = [k for k in subset_keys if k in df_final.columns]
                
                if valid_keys:
                    df_final.drop_duplicates(subset=valid_keys, keep='last', inplace=True)
            else:
                df_final = df_new

            df_final.to_csv(master_path, index=False, encoding='utf-8-sig')
            app_logger.info(f"Updated Master Data: {master_path}")
            return str(master_path)

        except Exception as e:
            app_logger.error(f"Lỗi khi lưu CSV: {e}")
            raise