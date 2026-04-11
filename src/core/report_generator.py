import unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from src.utils import app_logger

class ReportGenerator:
    def __init__(self, template_path: str = "docs/report_template.png"):
        self.template_path = Path.cwd()/template_path
        self.coords = {
            "main_bars": {
                "LC": {"x": 312, "y": 1081, "w": 448, "h": 28},
                "RC": {"x": 993, "y": 1081, "w": 467, "h": 28}
            },
            "lc_skills": [
                {"x": 490, "y": 1187, "w": 270, "h": 16},
                {"x": 490, "y": 1287, "w": 270, "h": 16},
                {"x": 490, "y": 1375, "w": 270, "h": 16},
                {"x": 490, "y": 1451, "w": 270, "h": 16}
            ],
            "rc_skills": [
                {"x": 1190, "y": 1175, "w": 270, "h": 16},
                {"x": 1190, "y": 1251, "w": 270, "h": 16},
                {"x": 1190, "y": 1339, "w": 270, "h": 16},
                {"x": 1190, "y": 1415, "w": 270, "h": 16},
                {"x": 1190, "y": 1483, "w": 270, "h": 16}
            ]
        }
        # --- Config Tọa Độ & Kích Thước ---
        self.color_main, self.color_date = "#1a1a1a", "#666666"
        self.color_lc, self.color_rc = "#1E88E5", "#2E7D32"

        # Load Font
        def load_font(path, size):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                return ImageFont.load_default()

        self.fonts = {
            "h1": load_font("src/fonts/SF-Pro-Display-Semibold.otf", 32),
            "date": load_font("src/fonts/SF-Compact-Display-Light.otf", 26),
            "score_medium": load_font("src/fonts/SF-Pro-Text-Semibold.otf", 32),
            "percentage": load_font("src/fonts/SF-Pro-Display-Regular.otf", 20),
            "badge_score": load_font("src/fonts/SF-Pro-Text-Bold.otf", 56)
        }

    def _normalize_name(self, text: str) -> str:
        """Loại bỏ dấu tiếng Việt và chuyển thành IN HOA"""
        if not text: return "UNKNOWN"
        # Chuẩn hóa unicode và loại bỏ dấu
        s = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode("utf-8")
        return s.upper()

    def _draw_fill(self, draw, box, ratio, color, is_main=False):
        """Hàm nội bộ chỉ chuyên nhận tọa độ để đổ màu và in chữ số"""
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        fill_w = int(w * ratio)
        
        # Vẽ khối màu
        if fill_w > 0:
            draw.rectangle([x, y, x + fill_w, y + h], fill=color)
            
        # In số
        font = self.fonts["score_medium"] if is_main else self.fonts["percentage"]
        text_val = str(int(ratio * 495)) if is_main else f"{int(ratio*100)}%"
        text_y = y - font.size - (12 if is_main else 6)
        
        text_w = draw.textlength(text_val, font=font)
        text_x = max(x, min(x + fill_w - (text_w / 2), x + w - text_w)) # Ép lề
            
        draw.text((text_x, text_y), text_val, font=font, fill=color)

    def generate_single_report(self, student_data: dict, output_dir: Path, image_source_dir: Path):
        if not self.template_path.exists():
            app_logger.error(f"Lỗi Template tại: {self.template_path.resolve()}")
            return
            
        try:
            bg = Image.open(self.template_path).convert("RGBA")
            draw = ImageDraw.Draw(bg)
            raw_name = student_data.get("Name", "UNKNOWN")
            
            # --- BƯỚC 1: Dán ảnh bài làm ---
            img_path = image_source_dir / f"{raw_name}.png"
            if img_path.exists():
                try:
                    paper = Image.open(img_path).convert("RGBA")
                    bg.paste(paper, (140, 120), paper)
                except Exception as e:
                    app_logger.warning(f"Lỗi dán ảnh: {e}")

            # --- BƯỚC 2: Chuyển tên In Hoa Không Dấu & In Ngày ---
            processed_name = self._normalize_name(raw_name)
            draw.text((140, 70), processed_name, font=self.fonts["h1"], fill=self.color_main)
            
            name_w = draw.textlength(processed_name, font=self.fonts["h1"])
            y_offset = 70 + (self.fonts["h1"].size - self.fonts["date"].size) - 2
            draw.text((140 + name_w + 20, y_offset), f"|  {student_data.get('Date', '')}", font=self.fonts["date"], fill=self.color_date)

            # --- BƯỚC 3: Vòng Ellipse & Total Score ---
            badge = {"x": 1270, "y": 40, "w": 180, "h": 150}
            draw.ellipse([badge["x"], badge["y"], badge["x"]+badge["w"], badge["y"]+badge["h"]], 
                         fill=None, outline=self.color_main, width=3)
            
            cx, cy = badge["x"] + badge["w"]/2, badge["y"] + badge["h"]/2
                      
            tot_str = str(student_data.get("Total", 0))
            draw.text((cx - draw.textlength(tot_str, font=self.fonts["badge_score"])/2, cy - 18), 
                      tot_str, font=self.fonts["badge_score"], fill=self.color_main)

            # --- BƯỚC 4: In Thanh Bar và Chỉ Số ---
            self._draw_fill(draw, self.coords["main_bars"]["LC"], student_data.get("LC", 0)/495.0, self.color_lc, is_main=True)
            self._draw_fill(draw, self.coords["main_bars"]["RC"], student_data.get("RC", 0)/495.0, self.color_rc, is_main=True)

            for i, box in enumerate(self.coords["lc_skills"], start=1):
                self._draw_fill(draw, box, float(student_data.get(f"lc_skill_{i}", 0.0)), self.color_lc)
                
            for i, box in enumerate(self.coords["rc_skills"], start=1):
                self._draw_fill(draw, box, float(student_data.get(f"rc_skill_{i}", 0.0)), self.color_rc)

            # --- LƯU FILE ---
            output_dir.mkdir(parents=True, exist_ok=True)
            bg.convert("RGB").save(output_dir / f"Report_{raw_name}.png")
            
        except Exception as e:
            app_logger.error(f"Lỗi Report: {e}")
    def generate_batch(self, results: list) -> tuple:
        """
        Xử lý xuất thẻ điểm hàng loạt. Tự động tạo cây thư mục.
        Trả về: (số_lượng_thành_công, đường_dẫn_thư_mục_lưu)
        """
        app_dir = Path.cwd()
        if not results:
            return 0, None

        # 1. Trích xuất Metadata để tạo tên thư mục
        first_record = results[0]
        date_str = first_record.get('Date', '')
        set_name = first_record.get('Set', 'UnknownSet')
        test_id = first_record.get('Test', 'UnknownTest')
        class_name = first_record.get('Class', 'UnknownClass')

        # Xử lý chuỗi ngày tháng
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            yyyymmdd = date_obj.strftime("%Y%m%d")
        except ValueError:
            yyyymmdd = date_str.replace("/", "").replace("-", "") 

        # 2. Xây dựng đường dẫn
        report_folder_name = f"{yyyymmdd}_{set_name.replace(" ", "")}_{test_id}"
        reports_dir = app_dir / "data" / report_folder_name
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        log_folder_name = f"{yyyymmdd}_{set_name.replace(" ", "")}_{test_id}_{class_name}"
        images_source_dir = app_dir / "logs" / log_folder_name

        # 3. Chạy vòng lặp xuất ảnh
        success_count = 0
        for student_data in results:
            self.generate_single_report(student_data, reports_dir, images_source_dir)
            success_count += 1

        return success_count, reports_dir