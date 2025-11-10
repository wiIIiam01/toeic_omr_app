# app_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont, messagebox
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path
import json
import sys 
import os
import pandas as pd # pandas không được dùng trực tiếp trong GUI, nhưng vẫn import nếu cần

# Import các module đã chia nhỏ
from state_manager import FormStateManager
from thread import ScoringThread

# Import các lớp xử lý cần thiết
from processing.utils import load_config as load_app_config, load_key, load_scoring_ref, save_results_to_excel
from processing.warp import WarpingProcessor
from processing.omr_engine import OMREngine
from processing.grade import GradeManager

KEY_PATH = Path("key.json")
SCORING_REF_PATH = 'scoring_ref.json'

class OMRLayoutDesign:
    
    def __init__(self, master: tk.Tk):
        # 1. Load configuration first
        self.config = self._load_config()
        self.P = self.config['PALETTE'] # Palette
        self.S = self.config['SIZES_AND_PADDING'] # Sizes
        self.D = self.config['DEFAULT_SETTINGS'] # Defaults

        self.master = master
        
        # Use config for title and geometry
        master.title(self.D['WINDOW_TITLE'])
        master.geometry(self.D['GEOMETRY']) 
        master.configure(bg=self.P['C_LIGHT'])
        
        # Cho phép các hàng và cột chính co giãn
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(1, weight=1) 
        
        # --- THIẾT LẬP STYLE (Cần thiết cho Combobox/Entry) ---
        s = ttk.Style()
        s.theme_use('clam') 
        
        default_font_family = self.D['FONT_FAMILY']
        input_font_size = self.S['INPUT_FONT_SIZE']
        input_pady = self.S['INPUT_PADY']
        
        # Cấu hình TCombobox
        s.configure('TCombobox', 
                    font=(default_font_family, input_font_size), 
                    padding=[10, input_pady], 
                    fieldbackground=self.P['C_LIGHT'],
                    foreground=self.P['C_PRIMARY_DARK'],
                    selectbackground=self.P['C_LIGHT'],
                    selectforeground=self.P['C_PRIMARY_DARK']) 

        # Cấu hình TEntry
        s.configure('TEntry', 
                    font=(default_font_family, input_font_size), 
                    padding=[10, input_pady], 
                    fieldbackground=self.P['C_LIGHT'],
                    foreground=self.P['C_PRIMARY_DARK'])
        
        # --- 2. TẢI VÀ CHUẨN BỊ DỮ LIỆU KEY & STATE MANAGER ---
        self.all_keys_data: Dict[str, Dict[str, str]] = {}
        self.set_names_list: List[str] = []
        self.app_config: Dict[str, Any] = {} # Config cho OMR Engine/Warping
        self.scoring_ref: Dict[str, Dict[str, int]] = {} # Bảng quy đổi điểm
        
        try:
            # Tải dữ liệu key từ file key.json (sử dụng hằng số đã import)
            self.all_keys_data = load_key(KEY_PATH) 
            self.set_names_list = list(self.all_keys_data.keys())
            # Tải config cho OMR
            self.app_config = load_app_config()
            # Tải bảng quy đổi điểm (sử dụng hằng số đã import)
            self.scoring_ref = load_scoring_ref(SCORING_REF_PATH)
            
        except FileNotFoundError as e:
            messagebox.showerror("Lỗi Cấu hình", f"Không tìm thấy file cần thiết: {e.filename}")
            print(f"Lỗi: Không tìm thấy file cần thiết: {e.filename}")
            # Dừng nếu các file cấu hình quan trọng bị thiếu
            self.master.destroy() 
            return
        except Exception as e:
            messagebox.showerror("Lỗi Cấu hình Key", f"Không thể tải dữ liệu cấu hình: {e}")
            print(f"Lỗi: Không thể tải dữ liệu cấu hình: {e}")
            self.master.destroy() 
            return
            
        # KHỞI TẠO STATE MANAGER (Import từ state_manager.py)
        self.form_state_manager = FormStateManager(self.all_keys_data)
            
        # --- 3. BIẾN TRẠNG THÁI UI (STATE VARIABLES CHO TKINTER) ---
        # Lấy giá trị mặc định từ State Manager
        self.selected_set_var = tk.StringVar(master, value=self.form_state_manager.UNSELECTED_SET)
        self.selected_id_var = tk.StringVar(master, value=self.form_state_manager.UNSELECTED_ID) 
        self.test_date_var = tk.StringVar(master, value=self.form_state_manager.UNSELECTED_DATE_HINT)
        
        # UI State 
        self.has_files_loaded = False 
        self.is_scoring = False # Trạng thái đang chấm điểm
        self.tree: Optional[ttk.Treeview] = None # Khởi tạo treeview là None
        
        # Biến lưu trữ tên file đã tồn tại để check unique (để tăng tốc độ)
        self.existing_filenames: Set[str] = set()

        # --- 4. TẠO CÁC KHUNG (FRAMES) CHÍNH ---
        self.top_controls_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.top_controls_frame.grid(row=0, column=0, sticky='ew')
        
        self.content_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=5)
        self.content_frame.grid(row=1, column=0, sticky='nsew')
        
        self.footer_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.footer_frame.grid(row=2, column=0, sticky='ew')

        # --- 5. ĐIỀN NỘI DUNG VÀO CÁC KHUNG ---
        self._create_top_controls()
        
        # Khởi tạo Drag & Drop/Table View lần đầu
        self._refresh_content_frame()
        
        self._create_footer_buttons()
        
        # --- 6. BIND SỰ KIỆN THAY ĐỔI KÍCH THƯỚC CỬA SỔ ---
        # Gọi cập nhật kích thước cột sau khi cửa sổ được vẽ lần đầu
        self.master.bind("<Configure>", self._resize_treeview_columns)
        
        # --- KHỞI TẠO CÁC NÚT & STATE BAN ĐẦU ---
        self._update_ui_state()
        
        self.parent_log_dir = Path.cwd().parent / "log"
        self.parent_log_dir.mkdir(exist_ok=True) # Đảm bảo thư mục này tồn tại
        
        # Thư mục log của phiên làm việc hiện tại (chưa biết cho đến khi bấm Start)
        self.current_result_dir: Optional[Path] = None


    def _load_config(self, filename='GUI_config.json'):
        # Giữ nguyên hàm tải config
        default_config = {
            "PALETTE": {"C_PRIMARY_DARK": '#222831', "C_SECONDARY_DARK": '#393E46', "C_ACCENT": '#00ADB5', "C_LIGHT": '#EEEEEE'},
            "SIZES_AND_PADDING": {"H_PAD": 20, "INPUT_FONT_SIZE": 20, "ACTION_FONT_SIZE": 11, "INPUT_PADY": 5, "ACTION_PADY": 5},
            "DEFAULT_SETTINGS": {"FONT_FAMILY": "Arial", "WINDOW_TITLE": "TOEIC OMR Scoring (Mặc Định)", "GEOMETRY": "800x600"}
        }
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(filename) # Ném lỗi để bắt ở __init__
        except json.JSONDecodeError:
            print(f"Lỗi: File cấu hình {filename} không hợp lệ. Sử dụng cấu hình mặc định.")
            return default_config

    # --- ACTION LOGIC: START SCORING ---

    def _update_ui_state(self, is_scoring: Optional[bool] = None):
        """Cập nhật trạng thái của các nút/combo box dựa trên trạng thái chấm điểm."""
        if is_scoring is not None:
            self.is_scoring = is_scoring

        # Cập nhật trạng thái của các nút/combo box
        state_control = 'disabled' if self.is_scoring else 'readonly'
        state_input = 'disabled' if self.is_scoring else 'normal'

        # Comboboxes
        self.set_combo.config(state=state_control)
        
        # Test ID Combo: chỉ kích hoạt khi đã chọn Set
        current_set = self.selected_set_var.get()
        if not self.is_scoring and current_set != self.form_state_manager.UNSELECTED_SET:
            self.id_combo.config(state='readonly')
        else:
            self.id_combo.config(state='disabled')

        # Date Entry
        self.date_entry.config(state=state_input)

        # Start Button (Đổi màu/văn bản/trạng thái)
        start_btn_text = "STOP" if self.is_scoring else "▶"
        start_btn_color = self.P['C_SECONDARY_DARK'] if self.is_scoring else self.P['C_ACCENT']
        
        # Tìm lại nút start
        start_btn_container = self.top_controls_frame.winfo_children()[0].winfo_children()[1] # R0, C1
        start_btn = start_btn_container.winfo_children()[0]

        start_btn.config(text=start_btn_text, bg=start_btn_color, 
                         activebackground=self.P['C_PRIMARY_DARK'],
                         activeforeground=self.P['C_LIGHT'])
        
        # Nút quản lý file
        if self.has_files_loaded:
            # Các nút Add/Remove/Clear trong table view
            file_management_frame = self.content_frame.winfo_children()[0].winfo_children()[1]
            for widget in file_management_frame.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.config(state=state_input)
        
        # Footer buttons
        # Nút Upload chỉ kích hoạt sau khi chấm điểm xong
        # Nút View Log
        footer_widgets = self.footer_frame.winfo_children()
        view_log_btn = footer_widgets[0]
        upload_btn = footer_widgets[1]

        view_log_btn.config(state=state_input) # Có thể xem log ngay cả khi đang chấm điểm nếu có log
        upload_btn.config(state='disabled') # Tạm thời disabled

    
    def _on_start_button_clicked(self):
        """Hàm xử lý khi nút START/STOP được nhấn."""
        
        if self.is_scoring:
            # STOP: Tạm thời không hỗ trợ
            messagebox.showwarning("Warning", "Không thể dừng quá trình chấm điểm hiện tại.")
            return

        is_valid, error_msg = self.form_state_manager.validate_and_update_state() 
        
        if is_valid:
            # 1. Khóa UI
            self._update_ui_state(is_scoring=True)

            # 2. Xóa các kết quả cũ
            self.form_state_manager.set_value('results', [], skip_validation=True)
            self._populate_treeview() # Reset bảng trạng thái

            # 3. Chạy Scoring Thread
            state = self.form_state_manager.state
            
            # Khởi tạo các processor
            warp_processor = WarpingProcessor(self.app_config)
            omr_engine = OMREngine(self.app_config)
            grade_manager = GradeManager(
                key_answer=state['key'], 
                scoring_ref=self.scoring_ref, 
                set_name=state['set_name'], 
                test_id=state['test_id'],
                test_date=state['test_date']
            )
            
            # Tạo thư mục 
            state = self.form_state_manager.state
            result_dir_name = (f"{state['test_date']}_{state['set_name']}_{state['test_id']}").replace(" ", "").replace("-", "")
            result_dir = self.parent_log_dir / result_dir_name
            result_dir.mkdir(exist_ok=True)
            self.current_result_dir = result_dir

            # Khởi tạo ScoringThread (Import từ scoring_thread.py)
            scoring_thread = ScoringThread(
                app_gui=self, # Truyền tham chiếu đến GUI
                image_files=state['image_files'],
                warp_processor=warp_processor,
                omr_engine=omr_engine,
                grade_manager=grade_manager,
                result_dir=result_dir
            )
            scoring_thread.start()

        else:
            messagebox.showwarning("Validation Failed", f"Warning:\n{error_msg}")

    # --- UI UPDATE CALLBACKS TỪ THREAD SCORING ---
    
    def on_file_graded(self, original_path: Path, result_dict: Optional[Dict[str, Any]], error_msg: Optional[str]):
        """Callback được gọi từ thread khi một file đã được chấm điểm/thất bại."""
        
        # 1. Cập nhật Treeview
        if self.tree is not None:
            iid = str(original_path)
            
            if result_dict:
                # Cập nhật kết quả thành công
                self.form_state_manager.get_value('results').append(result_dict)
                values = (
                    original_path.name, 
                    result_dict['Total'], 
                    result_dict['LC'].split('/')[0].strip(), # Chỉ lấy điểm số
                    result_dict['RC'].split('/')[0].strip(),
                    "✅ Done"
                )
                self.tree.item(iid, values=values)
            else:
                # Cập nhật kết quả thất bại
                values = (original_path.name, "-", "-", "-", f"❌ Failed: {error_msg[:40]}...")
                self.tree.item(iid, values=values)
                # Cập nhật màu chữ cho trạng thái lỗi (tùy chọn)
                self.tree.tag_configure('failed', foreground='red')
                self.tree.item(iid, tags=('failed',))
        
        # 2. Đảm bảo trạng thái UI hiển thị đúng (cần thiết khi có nhiều file)
        self.master.update_idletasks()
        
    def on_scoring_complete(self):
        """Callback được gọi khi tất cả các file đã được xử lý."""
        
        # Mở khóa UI
        self._update_ui_state(is_scoring=False)
        
        # Cập nhật trạng thái nút Upload (nếu có kết quả)
        if self.form_state_manager.get_value('results'):
            footer_widgets = self.footer_frame.winfo_children()
            upload_btn = footer_widgets[1]
            upload_btn.config(state='normal')

        messagebox.showinfo("Done", f"Đã chấm điểm xong {len(self.form_state_manager.get_value('image_files'))} bài.")

    # --- FILE MANAGEMENT LOGIC (Giữ nguyên) ---

    def _process_new_paths(self, new_paths: List[Path]):
        """
        Thêm các Path mới vào hàng đợi, loại bỏ trùng lặp và cập nhật UI.
        new_paths: Danh sách các Path (file hoặc folder) mới được chọn.
        """
        current_files: List[Path] = self.form_state_manager.get_value('image_files')
        
        new_valid_files: List[Path] = []
        
        for path in new_paths:
            if path.is_dir():
                # Xử lý thư mục: Quét các file .jpg/.jpeg
                folder_files = sorted([p for p in path.glob('*.jpg') if p.is_file()])
                folder_files.extend(sorted([p for p in path.glob('*.jpeg') if p.is_file()]))
                
                for file_path in folder_files:
                    if file_path.name not in self.existing_filenames:
                        new_valid_files.append(file_path)
                        self.existing_filenames.add(file_path.name)
            elif path.is_file() and path.suffix.lower() in ('.jpg', '.jpeg'):
                # Xử lý file: Chỉ thêm nếu là .jpg/.jpeg và không trùng lặp
                if path.name not in self.existing_filenames:
                    new_valid_files.append(path)
                    self.existing_filenames.add(path.name)
                    
        # Cập nhật hàng đợi
        if new_valid_files:
            current_files.extend(new_valid_files)
            self.form_state_manager.set_value('image_files', current_files, skip_validation=True)
            self.has_files_loaded = True
            self._refresh_content_frame(True) # Cập nhật chỉ bảng
            
        print(f"Total files in queue: {len(current_files)}")


    def _load_files(self):
        """Mở hộp thoại cho phép chọn file (multi-select) hoặc thư mục (single-select)."""
        
        # 1. Chọn file ảnh (multi-select)
        file_paths = filedialog.askopenfilenames(
            title="Chọn File Ảnh Bài Làm (.jpg/.jpeg)",
            filetypes=[("JPEG files", "*.jpg;*.jpeg")]
        )
        
        selected_paths: List[Path] = []
        if file_paths:
            selected_paths.extend([Path(p) for p in file_paths])

            
        if selected_paths:
            self._process_new_paths(selected_paths)


    def _remove_selected_files(self):
        """Loại bỏ các file đang được chọn trong Treeview khỏi hàng đợi."""
        if self.tree is None: return

        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một file để xóa.")
            return

        current_files: List[Path] = self.form_state_manager.get_value('image_files')
        
        # Sử dụng set để tìm kiếm nhanh hơn
        paths_to_remove = {Path(iid) for iid in selected_iids}
        
        # Lọc ra danh sách file mới
        new_files = [f for f in current_files if f not in paths_to_remove]
        
        # Cập nhật trạng thái và tên file tồn tại
        self.form_state_manager.set_value('image_files', new_files, skip_validation=True)
        self.existing_filenames = {f.name for f in new_files}
        
        # Cập nhật UI
        self.has_files_loaded = bool(new_files)
        self._refresh_content_frame()
        
        print(f"Removed {len(paths_to_remove)} files. Total files remaining: {len(new_files)}")


    def _clear_all_files(self):
        """Loại bỏ tất cả file trong hàng đợi."""
        if not self.form_state_manager.get_value('image_files'):
            messagebox.showinfo("Thông báo", "Hàng đợi đã trống.")
            return
            
        confirm = messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa tất cả các file ảnh đã tải?")
        if confirm:
            self.form_state_manager.set_value('image_files', [], skip_validation=True)
            self.existing_filenames.clear()
            self.has_files_loaded = False
            self._refresh_content_frame()
            print("Cleared all files in queue.")

    # --- INPUT LOGIC (Giữ nguyên) ---

    def _on_set_selected(self, event=None):
        """Hàm xử lý khi Set Combobox thay đổi."""
        selected_set = self.selected_set_var.get()
        self.form_state_manager.set_value('set_name', selected_set, skip_validation=True)
        
        if selected_set != self.form_state_manager.UNSELECTED_SET:
             self._update_test_id_combo(selected_set)
        else:
            self.selected_id_var.set(self.form_state_manager.UNSELECTED_ID)
            self.id_combo.config(values=[], state='disabled')
            
        self.form_state_manager.set_value('test_id', self.form_state_manager.UNSELECTED_ID, skip_validation=True)


    def _on_id_selected(self, event=None):
        """Hàm xử lý khi ID Combobox thay đổi."""
        selected_id = self.selected_id_var.get()
        self.form_state_manager.set_value('test_id', selected_id, skip_validation=True)

    def _update_test_id_combo(self, selected_set: str):
        """Cập nhật các Mã đề hợp lệ cho Combobox Mã đề."""
        self.id_combo.config(state='disabled')
        self.id_combo.set(self.form_state_manager.UNSELECTED_ID)
        
        if selected_set in self.all_keys_data:
            test_ids = list(self.all_keys_data[selected_set].keys())
            self.id_combo.config(values=test_ids)
            self.id_combo.config(state='readonly')
        else:
            self.id_combo.config(values=[])
            
        
    def _on_date_focus_in(self, event):
        """Xử lý khi Date Entry được focus, xóa hint."""
        if self.test_date_var.get() == self.form_state_manager.UNSELECTED_DATE_HINT:
            self.test_date_var.set('')

    def _on_date_focus_out(self, event):
        """Xử lý khi Date Entry mất focus, thêm hint nếu rỗng."""
        current_date = self.test_date_var.get()
        if current_date == '':
            current_date = self.form_state_manager.UNSELECTED_DATE_HINT
            self.test_date_var.set(current_date)
            
        self.form_state_manager.set_value('test_date', current_date, skip_validation=True)

    # --- UI LAYOUTS (Giữ nguyên) ---
            
    def _create_top_controls(self):
        frame = self.top_controls_frame
        
        frame.grid_columnconfigure(0, weight=6, uniform="top_columns") 
        frame.grid_columnconfigure(1, weight=4, uniform="top_columns") 

        # Khung chứa các input (Set, ID, Date)
        input_and_start_frame = tk.Frame(frame, bg=self.P['C_LIGHT'])
        input_and_start_frame.grid(row=0, column=0, sticky='ew')
        
        input_and_start_frame.grid_columnconfigure(0, weight=1) 
        input_and_start_frame.grid_columnconfigure(1, weight=0, minsize=80) 

        # Khung chứa Combobox/Entry
        input_area = tk.Frame(input_and_start_frame, bg=self.P['C_LIGHT'])
        input_area.grid(row=0, column=0, rowspan=2, sticky='nsew') 
        
        input_area.grid_columnconfigure(0, weight=7, uniform="inputs") 
        input_area.grid_columnconfigure(1, weight=3, uniform="inputs")
        
        # --- HÀNG 0: SET NAME & TEST ID/TEST ---
        self.set_combo = ttk.Combobox(input_area, textvariable=self.selected_set_var,
                                     values=self.set_names_list,
                                     state='readonly',
                                     )
        self.set_combo.grid(row=0, column=0, padx=(0, 5), pady=(0, self.S['INPUT_PADY']), sticky='ew')
        self.set_combo.bind('<<ComboboxSelected>>', self._on_set_selected)
        
        self.id_combo = ttk.Combobox(input_area, textvariable=self.selected_id_var,
                                     values=[], 
                                     state='disabled')
        self.id_combo.grid(row=0, column=1, padx=(5, 0), pady=(0, self.S['INPUT_PADY']), sticky='ew') 
        self.id_combo.bind('<<ComboboxSelected>>', self._on_id_selected)
        
        # --- HÀNG 1: DATE INPUT ---
        self.date_entry = ttk.Entry(input_area, textvariable=self.test_date_var, width=50) 
        self.date_entry.grid(row=1, column=0, columnspan=2, padx=(0, 0), 
                             pady=(self.S['INPUT_PADY'], 0), sticky='ew')
        self.date_entry.bind('<FocusIn>', self._on_date_focus_in)
        self.date_entry.bind('<FocusOut>', self._on_date_focus_out)
        
        # --- START BUTTON ---
        start_button_container = tk.Frame(input_and_start_frame, bg=self.P['C_LIGHT'])
        start_button_container.grid(row=0, column=1, rowspan=2, padx=(10, 0), pady=0, sticky='nsew') 
        
        start_button_container.grid_columnconfigure(0, weight=1)
        start_button_container.grid_rowconfigure(0, weight=1)

        start_button_font = tkfont.Font(family=self.D['FONT_FAMILY'], size=36, weight="bold")
        
        # Nút START 
        start_btn = tk.Button(start_button_container, 
                      text="▶", 
                      font=start_button_font, 
                      bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'], 
                      activebackground=self.P['C_PRIMARY_DARK'], 
                      activeforeground=self.P['C_ACCENT'],
                      relief='flat', bd=0, 
                      highlightthickness=0,
                      command=self._on_start_button_clicked) 
        
        start_btn.place(relx=0.5, rely=0.5, anchor='center')
        
        # --- 3.2. KHU VỰC INFO ---
        info_area = tk.Frame(frame, bg=self.P['C_LIGHT'])
        info_area.grid(row=0, column=1, rowspan=2, sticky='nse') 
        
        tk.Label(info_area, text="TOEIC OMR SCORING v1.0", 
                 font=(self.D['FONT_FAMILY'], 12, "bold"), 
                 fg=self.P['C_PRIMARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')
        
        tk.Label(info_area, text="Developed by Phong Nguyen", 
                 font=(self.D['FONT_FAMILY'], 10), 
                 fg=self.P['C_SECONDARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')
        
    def _create_drag_drop_area(self):
        # Nút Browse giờ đây sẽ gọi hàm mới
        frame = self.content_frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        drop_area = tk.Frame(frame, bg=self.P['C_LIGHT'], bd=0) 
        drop_area.grid(row=0, column=0, sticky='nsew') 
        
        drop_area.grid_columnconfigure(0, weight=1)
        drop_area.grid_rowconfigure(0, weight=1) 
        drop_area.grid_rowconfigure(4, weight=1) 
        
        image_placeholder = tk.Frame(drop_area, width=100, height=100, bg=self.P['C_LIGHT'], 
                                     highlightbackground=self.P['C_PRIMARY_DARK'], 
                                     highlightcolor=self.P['C_PRIMARY_DARK']) 
        
        image_placeholder.grid(row=1, column=0, pady=(10, 0)) 
        image_placeholder.grid_propagate(False) 

        image_placeholder.grid_columnconfigure(0, weight=1)
        image_placeholder.grid_rowconfigure(0, weight=1)
        
        icon_label = tk.Label(image_placeholder, 
                      text="     🖼️", 
                      font=(self.D['FONT_FAMILY'], 60), 
                      fg=self.P['C_ACCENT'], 
                      bg=self.P['C_LIGHT']
                      )
        icon_label.grid(row=0, column=0)

        # Nút Browse/Add 
        browse_btn = tk.Button(drop_area, 
                      text="Browse", 
                      font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                      bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                      relief='flat', bd=0, 
                      activebackground=self.P['C_PRIMARY_DARK'], 
                      activeforeground=self.P['C_ACCENT'],
                      padx=15, pady=self.S['ACTION_PADY'], 
                      command=self._load_files) 
        browse_btn.grid(row=2, column=0, pady=5, padx=20)

        tk.Label(drop_area, 
                 text="or drag a file here", 
                 font=(self.D['FONT_FAMILY'], 12), 
                 fg=self.P['C_PRIMARY_DARK'], 
                 bg=self.P['C_LIGHT']).grid(row=3, column=0, pady=(0, 10))


    def _create_table_view(self):
        frame = self.content_frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        # Khung chứa Bảng và các nút quản lý file
        table_and_controls_frame = tk.Frame(frame, bg=self.P['C_LIGHT'])
        table_and_controls_frame.grid(row=0, column=0, sticky='nsew')
        
        table_and_controls_frame.grid_columnconfigure(0, weight=1)
        table_and_controls_frame.grid_rowconfigure(0, weight=1) # Dành cho Treeview

        # --- NÚT QUẢN LÝ FILE (HÀNG 1) ---
        file_management_frame = tk.Frame(table_and_controls_frame, bg=self.P['C_LIGHT'])
        file_management_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
        
        # Căn chỉnh các nút sang trái
        file_management_frame.grid_columnconfigure(0, weight=1) 
        
        add_btn = tk.Button(file_management_frame, text="Add", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self._load_files) 
        add_btn.grid(row=0, column=1, padx=0, pady=0)
        
        remove_btn = tk.Button(file_management_frame, text="Remove", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self._remove_selected_files) 
        remove_btn.grid(row=0, column=2, padx=0, pady=0)
        
        clear_btn = tk.Button(file_management_frame, text="Clear", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self._clear_all_files) 
        clear_btn.grid(row=0, column=3, padx=0, pady=0)

        # --- BẢNG (TREEVIEW) (HÀNG 0) ---
        table_container = tk.Frame(table_and_controls_frame, bg=self.P['C_LIGHT'])
        table_container.grid(row=0, column=0, sticky='nsew')
        
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        scrollbar_y = ttk.Scrollbar(table_container, orient="vertical")
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        
        columns = ("name", "total_score", "lc_score", "rc_score", "status")
        # Khởi tạo Treeview
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", yscrollcommand=scrollbar_y.set, selectmode='extended')
        scrollbar_y.config(command=self.tree.yview)
        
        self.tree.heading("name", text="Name", anchor='center')
        self.tree.heading("total_score", text="Total", anchor='center')
        self.tree.heading("lc_score", text="LC", anchor='center')
        self.tree.heading("rc_score", text="RC", anchor='center')
        self.tree.heading("status", text="Status", anchor='center')
        
        # Đổ dữ liệu vào bảng
        self._populate_treeview()

        self.tree.grid(row=0, column=0, sticky='nsew')
        
        # Cần gọi cập nhật kích thước cột lần đầu sau khi Treeview được tạo
        self.master.after(10, self._resize_treeview_columns)


    def _populate_treeview(self):
        """Đổ dữ liệu từ State Manager vào Treeview."""
        if self.tree is None: return
        
        # Xóa tất cả các mục hiện có
        for item in self.tree.get_children():
            self.tree.delete(item)

        image_files_list: List[Path] = self.form_state_manager.get_value('image_files')
        
        for img_path in image_files_list:
            file_name = img_path.name
            # iid (ID của item) là đường dẫn Path đầy đủ để dễ dàng remove/update
            initial_values = (file_name, "-", "-", "-", "Pending")
            self.tree.insert("", "end", iid=str(img_path), values=initial_values)


    def _refresh_content_frame(self, only_update_table: bool = False):
        """Xóa và vẽ lại khu vực nội dung (Drag&Drop hoặc Table View)."""
        
        if only_update_table and self.has_files_loaded and self.tree is not None:
            # Nếu chỉ cập nhật bảng và bảng đang hiển thị
            self._populate_treeview()
            self._resize_treeview_columns()
            return

        # Xóa nội dung hiện tại của content_frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        # Hiển thị nội dung mới
        if self.has_files_loaded:
            # Nếu có file, hiển thị bảng và các nút quản lý file
            self._create_table_view()
        else:
            # Nếu không có file, hiển thị khu vực Drag&Drop
            self.tree = None 
            self._create_drag_drop_area()

        # Cần cập nhật trạng thái các nút sau khi refresh frame
        self.master.after(10, self._update_ui_state)


    def _resize_treeview_columns(self, event=None):
        """Cập nhật chiều rộng cột dựa trên chiều rộng hiện tại của cửa sổ."""
        if self.tree is None or not self.master.winfo_ismapped():
            return

        # Chiều rộng cửa sổ chính - (H_PAD * 2) - khoảng trống của scrollbar (20)
        total_width = self.master.winfo_width() - (self.S['H_PAD'] * 2) - 20
        
        if total_width < 100:
            return 

        # Tỉ lệ chiều dài cột (4:1.5:1:1:2.5, Tổng = 10)
        ratios = {
            "name": 4.0, "total_score": 1.5,
            "lc_score": 1.0, "rc_score": 1.0,
            "status": 2.5,
        }
        
        total_ratio = sum(ratios.values())
        
        for col_id, ratio in ratios.items():
            new_width = int(total_width * ratio / total_ratio)
            self.tree.column(col_id, width=new_width, minwidth=20) 
        
        # Điều chỉnh cột "name" để nó co giãn
        self.tree.column("name", stretch=tk.YES)


    def _create_footer_buttons(self):
        frame = self.footer_frame
        
        # Căn chỉnh các nút sang phải
        frame.grid_columnconfigure(0, weight=1)
        
        view_log_btn = tk.Button(frame, text="View Log", 
                                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                                 bg=self.P['C_SECONDARY_DARK'], fg=self.P['C_LIGHT'],
                                 activebackground=self.P['C_PRIMARY_DARK'], 
                                 activeforeground=self.P['C_SECONDARY_DARK'],
                                 relief='flat', bd=0, 
                                 padx=15, pady=self.S['ACTION_PADY'],
                                 command=self._on_view_log_clicked) 
        view_log_btn.grid(row=0, column=1, padx=5, pady=5)
        
        upload_btn = tk.Button(frame, text="Save & Upload", 
                               font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                               bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                               activebackground=self.P['C_PRIMARY_DARK'],
                               activeforeground=self.P['C_ACCENT'],
                               relief='flat', bd=0, 
                               padx=15, pady=self.S['ACTION_PADY'],
                               state='disabled', # Mặc định disabled
                               command=self._on_save_and_upload_clicked)
        upload_btn.grid(row=0, column=2, padx=5, pady=5)

    def _on_view_log_clicked(self):
        path_to_open = None
        
        # 1. Ưu tiên thư mục của phiên hiện tại (nếu đã chạy Start)
        if self.current_result_dir and self.current_result_dir.exists():
            path_to_open = self.current_result_dir
        # 2. Nếu không, mở thư mục log cha mặc định
        elif self.parent_log_dir.exists():
            path_to_open = self.parent_log_dir
        else:
            messagebox.showwarning("Không tìm thấy", "Không thể tìm thấy thư mục log.")
            return

        # 3. Mở thư mục (đa nền tảng)
        try:
            path_str = str(path_to_open.resolve())
            
            if sys.platform == "win32":
                os.startfile(path_str)
            elif sys.platform == "darwin": # macOS
                os.system(f'open "{path_str}"')
            else: # Linux
                os.system(f'xdg-open "{path_str}"')
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")
    
    def _on_save_and_upload_clicked(self):
        
        # 1. Lấy danh sách kết quả từ state manager
        results = self.form_state_manager.get_value('results')
        
        if not results:
            messagebox.showwarning("Không có dữ liệu", "Không có kết quả nào để lưu.")
            return

        try:
            # 2. Lấy thông tin trạng thái hiện tại
            state = self.form_state_manager.state
            
            # 3. TÁI TẠO LẠI 'result_dir'
            result_dir_name = (f"{state['test_date']}_{state['set_name']}_{state['test_id']}").replace(" ", "").replace("-", "")
            parent_log_dir = Path.cwd().parent / "log"
            result_dir = parent_log_dir / result_dir_name
            
            saved_path = save_results_to_excel(
                results=results,
                result_dir=result_dir,
                set_name=state['set_name'],
                test_id=state['test_id']
            )
            
            messagebox.showinfo("Done", f"Đã lưu kết quả tại:\n{saved_path.resolve()}")

        except Exception as e:
            messagebox.showerror("Lỗi khi lưu Excel", f"Đã xảy ra lỗi: {e}")
            print(f"Lỗi chi tiết khi lưu Excel: {e}")