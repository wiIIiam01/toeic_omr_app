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
    def save_results_to_excel(results: List[Dict[str, Any]], result_dir: Path, file_name_prefix: str = "") -> Optional[Path]:
        """
        Lưu kết quả ra Excel. Tự động nối (append) nếu file đã tồn tại.
        """
        if not results:
            app_logger.warning("No results to save.")
            return None

        try:
            result_dir.mkdir(parents=True, exist_ok=True)
            
            # Tự động lấy tên từ thư mục nếu không truyền prefix
            prefix = file_name_prefix if file_name_prefix else result_dir.name
            excel_path = result_dir / f"{prefix}_summary.xlsx"

            df_new = pd.DataFrame(results)
            # Ép kiểu Date sang string để tránh lỗi Excel format khi merge
            if 'Date' in df_new.columns:
                df_new['Date'] = df_new['Date'].astype(str)

            if excel_path.exists():
                app_logger.info(f"Appending to existing Excel: {excel_path}")
                try:
                    df_old = pd.read_excel(excel_path)
                    if 'Date' in df_old.columns:
                        df_old['Date'] = df_old['Date'].astype(str)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                except Exception as e:
                    app_logger.warning(f"Could not read existing Excel ({e}). Overwriting.")
                    df_combined = df_new
            else:
                df_combined = df_new

            df_combined.to_excel(excel_path, index=False)
            app_logger.info(f"Results saved to: {excel_path}")
            return excel_path

        except Exception as e:
            app_logger.error(f"Failed to save Excel: {e}")
            raise
        
    @staticmethod
    def save_results_to_csv(results: List[Dict[str, Any]], result_dir: Path, file_name_prefix: str = "") -> Optional[Path]:
        """
        Lưu kết quả ra CSV. Sử dụng mode 'a' để tối ưu hiệu suất.
        """
        if not results:
            app_logger.warning("Không có kết quả để lưu.")
            return None

        try:
            result_dir.mkdir(parents=True, exist_ok=True)
            prefix = file_name_prefix if file_name_prefix else result_dir.name
            csv_path = result_dir / f"{prefix}_summary.csv"

            df_new = pd.DataFrame(results)
            
            # Đảm bảo cột Date luôn là string để thống nhất dữ liệu
            if 'Date' in df_new.columns:
                df_new['Date'] = df_new['Date'].astype(str)

            file_exists = csv_path.exists()

            # Logic ghi file:
            # - Nếu file tồn tại: mode='a' (ghi tiếp), header=False (không ghi lại tiêu đề cột)
            # - Nếu file chưa có: mode='w' (ghi mới), header=True
            df_new.to_csv(
                csv_path, 
                mode='a' if file_exists else 'w', 
                index=False, 
                header=not file_exists, 
                encoding='utf-8-sig' # Đảm bảo mở bằng Excel không lỗi font tiếng Việt
            )
            
            app_logger.info(f"Đã cập nhật kết quả vào: {csv_path.name}")
            return csv_path

        except Exception as e:
            app_logger.error(f"Lỗi khi lưu CSV: {e}")
            raise