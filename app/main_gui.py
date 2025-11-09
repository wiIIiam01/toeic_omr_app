import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont, messagebox
import math
import json
import sys 
import os
import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from threading import Thread
from typing import Dict, Any

# Import các thành phần xử lý từ logic chính
# Lưu ý: Cần đảm bảo các file này đã được chuẩn hóa (như utils, warp, omr_engine, grade)
try:
    from processing.utils import load_config as load_app_config, load_key, load_scoring_ref, get_answer_key, get_answer_parts_ranges
    from processing.warp import WarpingProcessor
    from processing.omr_engine import OMREngine
    from processing.grade import GradeManager
except ImportError as e:
    messagebox.showerror("Lỗi Import", f"Không thể tải các mô-đun xử lý: {e}. Vui lòng đảm bảo cấu trúc thư mục processing/ là chính xác.")
    sys.exit(1)


class OMRLayoutDesign:
    
    def __init__(self, master: tk.Tk):
        # 1. Load configuration first
        self.config = self._load_gui_config()
        self.P = self.config['PALETTE'] # Palette
        self.S = self.config['SIZES_AND_PADDING'] # Sizes
        self.D = self.config['DEFAULT_SETTINGS'] # Defaults

        self.master = master
        self.all_keys_data = {}
        self.scoring_ref = {}
        self.app_config = {}

        # Biến trạng thái
        self.folder_path = tk.StringVar(value="Vui lòng chọn thư mục ảnh...")
        self.test_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d_%Hh%Mm"))
        
        # Biến Combobox
        self.selected_set = tk.StringVar()
        self.selected_id = tk.StringVar()
        
        # Sử dụng config cho title và geometry
        master.title(self.D['WINDOW_TITLE'])
        master.geometry(self.D['GEOMETRY']) 
        master.configure(bg=self.P['C_LIGHT'])
        
        # Cho phép các hàng và cột chính co giãn
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(1, weight=1) 
        
        # --- TẢI DỮ LIỆU CẦN THIẾT ---
        self._load_app_data()

        # --- THIẾT LẬP STYLE ---
        self._setup_styles()
        
        # --- THIẾT LẬP CÁC FRAME ---
        self.header_frame = self._create_header_frame()
        self.body_frame = self._create_body_frame()
        self.table_frame = self._create_table_frame()
        self.footer_frame = self._create_footer_frame()
        
        # --- THIẾT LẬP CÁC WIDGET TRONG FRAME ---
        self._setup_header_widgets()
        self._setup_table_widgets()
        self._setup_footer_widgets()

    def _load_gui_config(self, filename: Path = Path("GUI_config.json")) -> Dict[str, Any]:
        """Tải file cấu hình GUI."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Lỗi Cấu hình", f"Không tìm thấy file cấu hình {filename}.")
            sys.exit(1)

    def _load_app_data(self):
        """Tải config, key và scoring ref cho OMR Engine."""
        try:
            self.app_config = load_app_config(Path("config.json"))
            self.all_keys_data = load_key(Path("key.json"))
            self.scoring_ref = load_scoring_ref("scoring_ref.json")
            
            # Khởi tạo các biến combobox với dữ liệu đầu tiên nếu có
            set_names = list(self.all_keys_data.keys())
            if set_names:
                self.selected_set.set(set_names[0])
                test_ids = list(self.all_keys_data[set_names[0]].keys())
                if test_ids:
                    self.selected_id.set(test_ids[0])

        except Exception as e:
            messagebox.showerror("Lỗi Dữ liệu", f"Lỗi khi tải dữ liệu ứng dụng (config, key, scoring_ref): {e}")
            sys.exit(1)


    def _setup_styles(self):
        """Thiết lập styles cho các widget Tkinter."""
        s = ttk.Style()
        s.theme_use('clam') 
        
        default_font_family = self.D['FONT_FAMILY']
        input_font_size = self.S['INPUT_FONT_SIZE']
        input_pady = self.S['INPUT_PADY']
        
        # Cấu hình TCombobox
        s.configure('TCombobox', 
                    fieldbackground=self.P['C_SECONDARY_DARK'], 
                    background=self.P['C_SECONDARY_DARK'],
                    foreground=self.P['C_LIGHT'], 
                    selectbackground=self.P['C_ACCENT'],
                    selectforeground=self.P['C_PRIMARY_DARK'],
                    font=(default_font_family, input_font_size))
        s.map('TCombobox', 
              fieldbackground=[('readonly', self.P['C_SECONDARY_DARK'])])

        # Cấu hình Treeview (Bảng hiển thị kết quả)
        s.configure('Treeview.Heading', 
                    font=(default_font_family, self.S['ACTION_FONT_SIZE'], 'bold'), 
                    background=self.P['C_PRIMARY_DARK'], 
                    foreground=self.P['C_ACCENT'], 
                    bordercolor=self.P['C_SECONDARY_DARK'])
        s.configure('Treeview', 
                    font=(default_font_family, 10), 
                    background=self.P['C_SECONDARY_DARK'], 
                    foreground=self.P['C_LIGHT'], 
                    rowheight=25)
        s.map('Treeview', 
              background=[('selected', self.P['C_ACCENT'])], 
              foreground=[('selected', self.P['C_PRIMARY_DARK'])])

    def _create_header_frame(self):
        """Tạo và đặt khung tiêu đề chứa các tùy chọn."""
        frame = tk.Frame(self.master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        frame.grid(row=0, column=0, sticky='ew')
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _create_body_frame(self):
        """Tạo và đặt khung chứa nút Browse/Drag."""
        frame = tk.Frame(self.master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        frame.grid(row=1, column=0, sticky='nsew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        return frame
    
    def _create_table_frame(self):
        """Tạo và đặt khung chứa bảng kết quả."""
        frame = tk.Frame(self.body_frame, bg=self.P['C_LIGHT'])
        frame.grid(row=0, column=0, sticky='nsew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        return frame

    def _create_footer_frame(self):
        """Tạo và đặt khung chân trang chứa các nút hành động."""
        frame = tk.Frame(self.master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=5)
        frame.grid(row=2, column=0, sticky='ew')
        frame.grid_columnconfigure(0, weight=1) # Căn chỉnh các nút sang phải
        return frame
    
    def _update_test_id_combobox(self, event):
        """Cập nhật danh sách Mã đề khi Bộ đề (Set) thay đổi."""
        selected_set_name = self.selected_set.get()
        if selected_set_name in self.all_keys_data:
            test_ids = list(self.all_keys_data[selected_set_name].keys())
            self.test_id_combobox['values'] = test_ids
            if test_ids:
                self.selected_id.set(test_ids[0])
            else:
                self.selected_id.set("")
        else:
            self.test_id_combobox['values'] = []
            self.selected_id.set("")

    def _select_folder(self):
        """Mở hộp thoại để chọn thư mục ảnh."""
        folder = filedialog.askdirectory(title="Chọn thư mục chứa ảnh bài làm (.jpg)")
        if folder:
            self.folder_path.set(folder)
            self.browse_label.config(text=f"Đã chọn: {folder}")
            self.process_btn.config(state=tk.NORMAL) # Bật nút xử lý
            messagebox.showinfo("Thành công", f"Đã chọn thư mục: {Path(folder).name}")
        else:
            self.process_btn.config(state=tk.DISABLED) # Tắt nút xử lý nếu không chọn gì

    def _setup_header_widgets(self):
        """Cấu hình và đặt các widget trong khung tiêu đề."""
        frame = self.header_frame
        
        # --- Combobox Set (Bộ đề) ---
        tk.Label(frame, text="Bộ đề (Set):", bg=self.P['C_LIGHT'], fg=self.P['C_PRIMARY_DARK'], 
                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold")).grid(row=0, column=0, sticky='w')
        
        set_names = list(self.all_keys_data.keys())
        self.set_combobox = ttk.Combobox(frame, textvariable=self.selected_set, values=set_names, state='readonly')
        self.set_combobox.grid(row=1, column=0, sticky='ew', padx=5, pady=self.S['INPUT_PADY'])
        self.set_combobox.bind('<<ComboboxSelected>>', self._update_test_id_combobox)
        
        
        # --- Combobox Test ID (Mã đề) ---
        tk.Label(frame, text="Mã đề (Test ID):", bg=self.P['C_LIGHT'], fg=self.P['C_PRIMARY_DARK'], 
                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold")).grid(row=0, column=1, sticky='w')
        
        test_ids = list(self.all_keys_data.get(self.selected_set.get(), {}).keys())
        self.test_id_combobox = ttk.Combobox(frame, textvariable=self.selected_id, values=test_ids, state='readonly')
        self.test_id_combobox.grid(row=1, column=1, sticky='ew', padx=5, pady=self.S['INPUT_PADY'])
        
        # --- Entry Test Date (Ngày thi) ---
        tk.Label(frame, text="Tên Phiên (VD: 2025-05-20):", bg=self.P['C_LIGHT'], fg=self.P['C_PRIMARY_DARK'], 
                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold")).grid(row=0, column=2, sticky='w')
        
        test_date_entry = ttk.Entry(frame, textvariable=self.test_date, 
                                    font=(self.D['FONT_FAMILY'], self.S['INPUT_FONT_SIZE']),
                                    background=self.P['C_SECONDARY_DARK'], foreground=self.P['C_LIGHT'])
        test_date_entry.grid(row=1, column=2, sticky='ew', padx=5, pady=self.S['INPUT_PADY'])
        
        # Cấu hình cân nặng cho cột
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)

        # Cập nhật lần đầu cho test_id
        self._update_test_id_combobox(None)

    def _setup_table_widgets(self):
        """Cấu hình và đặt bảng Treeview để hiển thị kết quả."""
        frame = self.table_frame
        
        # Khung chứa nút Browse và nút xử lý
        action_frame = tk.Frame(frame, bg=self.P['C_LIGHT'], pady=10)
        action_frame.pack(fill='x')
        action_frame.grid_columnconfigure(0, weight=1)
        
        # Nút Browse (Chọn thư mục)
        browse_btn = tk.Button(action_frame, text="Browse/Drag a file here...", 
                               font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                               bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                               activebackground=self.P['C_PRIMARY_DARK'], activeforeground=self.P['C_ACCENT'],
                               relief='flat', bd=0, 
                               padx=15, pady=self.S['ACTION_PADY'] * 2,
                               command=self._select_folder)
        browse_btn.grid(row=0, column=0, sticky='e', padx=5)

        # Nút Xử lý (Process) - Ban đầu bị ẩn
        self.process_btn = tk.Button(action_frame, text="BẮT ĐẦU CHẤM BÀI", 
                                     font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                                     bg='#4CAF50', fg='white',
                                     activebackground='#388E3C', activeforeground='white',
                                     relief='flat', bd=0, 
                                     padx=15, pady=self.S['ACTION_PADY'] * 2,
                                     command=self._start_processing_thread,
                                     state=tk.DISABLED) # Bị vô hiệu hóa ban đầu
        self.process_btn.grid(row=0, column=1, sticky='w', padx=5)
        
        # Label hiển thị đường dẫn thư mục
        self.browse_label = tk.Label(action_frame, textvariable=self.folder_path, bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                     font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE']))
        self.browse_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(5, 10))

        # --- Bảng Treeview ---
        # Khung riêng cho Treeview và Scrollbar
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbar dọc
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side='right', fill='y')
        
        # Định nghĩa các cột
        COLUMNS = ["Tên File", "Tổng", "LC", "RC", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "Trạng thái"]
        column_widths = [150, 60, 60, 60, 40, 40, 40, 40, 40, 40, 40, 150]
        
        self.tree = ttk.Treeview(tree_frame, columns=COLUMNS, show='headings', yscrollcommand=vsb.set)
        vsb.config(command=self.tree.yview)

        # Cấu hình các cột
        for col, width in zip(COLUMNS, column_widths):
            self.tree.heading(col, text=col, anchor='center')
            self.tree.column(col, width=width, anchor='center', stretch=False)
            
        self.tree.pack(fill='both', expand=True)

    def _setup_footer_widgets(self):
        """Cấu hình và đặt các widget trong khung chân trang."""
        frame = self.footer_frame
        
        # Nút View Log 
        view_log_btn = tk.Button(frame, text="View Log", 
                                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                                 bg=self.P['C_SECONDARY_DARK'], fg=self.P['C_LIGHT'],
                                 activebackground=self.P['C_PRIMARY_DARK'], 
                                 activeforeground=self.P['C_SECONDARY_DARK'],
                                 relief='flat', bd=0, 
                                 padx=15, pady=self.S['ACTION_PADY']) 
        view_log_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # Nút Save & Upload 
        upload_btn = tk.Button(frame, text="Lưu & Xuất Excel", 
                               font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                               bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                               activebackground=self.P['C_PRIMARY_DARK'],
                               activeforeground=self.P['C_ACCENT'],
                               relief='flat', bd=0, 
                               padx=15, pady=self.S['ACTION_PADY'],
                               command=self._save_results_to_excel) 
        upload_btn.grid(row=0, column=2, padx=5, pady=5)


    # =========================================================================
    # --- LOGIC XỬ LÝ ẢNH (Tích hợp từ main.py) ---
    # =========================================================================

    def _start_processing_thread(self):
        """Khởi động luồng xử lý riêng để tránh đóng băng GUI."""
        # Xóa kết quả cũ
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        # Vô hiệu hóa các nút điều khiển trong khi xử lý
        self.process_btn.config(state=tk.DISABLED, text="ĐANG XỬ LÝ...")
        self.set_combobox.config(state=tk.DISABLED)
        self.test_id_combobox.config(state=tk.DISABLED)
        
        # Bắt đầu luồng xử lý
        self.all_results_list = [] # Reset danh sách kết quả
        Thread(target=self._process_images_logic).start()

    def _process_images_logic(self):
        """Luồng chính xử lý ảnh OMR, tương tự main.py."""
        selected_set = self.selected_set.get()
        selected_id = self.selected_id.get()
        image_dir = self.folder_path.get()
        session_name = self.test_date.get()
        
        # 1. Kiểm tra điều kiện đầu vào
        if not selected_set or not selected_id or not image_dir or not Path(image_dir).is_dir():
            self._on_processing_complete("Lỗi: Vui lòng chọn Bộ đề, Mã đề và thư mục ảnh hợp lệ.")
            return

        try:
            # Lấy key và khởi tạo các engine
            key_raw = get_answer_key(self.all_keys_data, selected_set, selected_id)
            
            warp_processor = WarpingProcessor(self.app_config)
            omr_engine = OMREngine(self.app_config)
            grade_manager = GradeManager(key_raw, self.scoring_ref, selected_set, selected_id)

            image_files = list(Path(image_dir).glob('*.jpg')) # Chỉ quét .jpg
            if not image_files:
                self._on_processing_complete(f"Không tìm thấy file ảnh .jpg nào trong thư mục: {Path(image_dir).name}")
                return

            result_dir = Path(image_dir) / f"KET_QUA_{session_name}"
            
            # 2. Vòng lặp xử lý từng file
            for img_path in image_files:
                base_name = img_path.stem
                
                # Cập nhật trạng thái trong GUI
                self.tree.insert('', 'end', values=(base_name, '', '', '', '', '', '', '', '', '', '', "⏳ Đang xử lý..."))
                self.master.update()
                
                try:
                    # Đọc ảnh (dùng imdecode để tránh lỗi Unicode trên Windows)
                    img_bgr = cv2.imdecode(np.fromfile(str(img_path), np.uint8), cv2.IMREAD_UNCHANGED)
                    if img_bgr is None:
                        raise RuntimeError("Không thể đọc/giải mã file ảnh.")

                    # a. Warping
                    img_warped_bgr, img_warped_binary = warp_processor.process_warping(img_bgr)
                    
                    # b. OMR Engine
                    answers_list, _, image_with_grid = omr_engine.process_omr(
                        img_warped_binary, 
                        img_warped_bgr
                    )

                    # c. Grading
                    parts, answers_string = grade_manager.grade_answers(answers_list)

                    # d. Save result image and format data
                    grade_manager.save_result_image(base_name, image_with_grid, result_dir)
                    row_dict = grade_manager.format_result(base_name, parts, answers_string)
                    self.all_results_list.append(row_dict)
                    
                    # Cập nhật Treeview với kết quả thành công
                    self._update_treeview_row(base_name, row_dict, "✅ HOÀN THÀNH")
                
                except ValueError as ve:
                    self._update_treeview_row(base_name, None, f"❌ LỖI: {ve}")
                except RuntimeError as re:
                    self._update_treeview_row(base_name, None, f"❌ LỖI HỆ THỐNG: {re}")
                except Exception as e:
                    self._update_treeview_row(base_name, None, f"❌ LỖI CHUNG: {e}")
            
            self._on_processing_complete(f"Đã hoàn thành chấm {len(image_files)} bài. Kết quả nằm trong {result_dir.name}")

        except Exception as e:
            self._on_processing_complete(f"Lỗi Khởi tạo/Tổng quan: {e}")


    def _update_treeview_row(self, file_name: str, result_data: Dict[str, Any] | None, status: str):
        """Cập nhật hoặc thêm hàng mới vào Treeview."""
        # Tìm hàng dựa trên Tên File
        item_id = None
        for item in self.tree.get_children():
            if self.tree.item(item, 'values')[0] == file_name:
                item_id = item
                break
        
        # Nếu không tìm thấy, thêm hàng mới (thường chỉ xảy ra khi lỗi ngay từ đầu)
        if not item_id:
            # Tìm item có trạng thái '⏳ Đang xử lý...' và tên file trùng
            for item in self.tree.get_children():
                 if self.tree.item(item, 'values')[0] == file_name and self.tree.item(item, 'values')[-1] == "⏳ Đang xử lý...":
                    item_id = item
                    break
            
            if not item_id:
                 # Nếu vẫn không tìm thấy, tạo hàng mới (dự phòng)
                item_id = self.tree.insert('', 'end', values=(file_name, '', '', '', '', '', '', '', '', '', '', status))
        
        # Cập nhật giá trị
        if result_data:
            values = (
                file_name,
                result_data.get('Total', ''),
                result_data.get('LC', ''),
                result_data.get('RC', ''),
                result_data.get('Part 1', '').split(' / ')[0], # Chỉ lấy số câu đúng
                result_data.get('Part 2', '').split(' / ')[0],
                result_data.get('Part 3', '').split(' / ')[0],
                result_data.get('Part 4', '').split(' / ')[0],
                result_data.get('Part 5', '').split(' / ')[0],
                result_data.get('Part 6', '').split(' / ')[0],
                result_data.get('Part 7', '').split(' / ')[0],
                status
            )
            self.tree.item(item_id, values=values)
            # Tự động cuộn xuống
            self.tree.yview_moveto(1)
        else:
             # Cập nhật chỉ trạng thái khi có lỗi
            current_values = list(self.tree.item(item_id, 'values'))
            current_values[-1] = status
            self.tree.item(item_id, values=current_values)

        self.master.update_idletasks() # Đảm bảo GUI được vẽ lại

    def _on_processing_complete(self, message: str):
        """Hoàn tất xử lý, cập nhật trạng thái nút và thông báo."""
        # Kích hoạt lại các nút điều khiển
        self.process_btn.config(state=tk.NORMAL, text="BẮT ĐẦU CHẤM BÀI")
        self.set_combobox.config(state='readonly')
        self.test_id_combobox.config(state='readonly')
        
        messagebox.showinfo("Hoàn thành", message)


    def _save_results_to_excel(self):
        """Lưu danh sách kết quả (từ self.all_results_list) ra file Excel."""
        if not self.all_results_list:
            messagebox.showwarning("Lỗi Lưu File", "Không có kết quả nào để lưu. Vui lòng chấm bài trước.")
            return

        # Hỏi người dùng vị trí lưu file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"{self.selected_set.get()}_{self.selected_id.get()}_{self.test_date.get()}_KET_QUA.xlsx",
            title="Lưu kết quả ra file Excel"
        )

        if file_path:
            try:
                df = pd.DataFrame(self.all_results_list)
                df.to_excel(file_path, index=False)
                messagebox.showinfo("Thành công", f"Đã lưu kết quả thành công tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi Lưu File", f"Lỗi khi lưu file Excel: {e}")

if __name__ == '__main__':
    # Kiểm tra và cài đặt font nếu không phải Windows
    if sys.platform != "win32":
        try:
            from tkfont import Font
        except ImportError:
            print("Vui lòng cài đặt font tkfont nếu gặp lỗi font trên Linux/Mac.")
            
    root = tk.Tk()
    app = OMRLayoutDesign(root)
    root.mainloop()