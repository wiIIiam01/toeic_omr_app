import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont, filedialog
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys
import os

from .state_manager import FormStateManager
from .components import DragDropArea, FileTableView

from src.utils import app_logger, FileHandler
from src.core import WarpingProcessor, OMREngine, GradeManager
from src.workers import ScoringWorker 

# Đường dẫn (Relative path từ thư mục chạy main.py - tức là thư mục gốc dự án)
# Cấu trúc mới: config nằm ở root/config
CONFIG_PATH = Path("config/app_config.json")
KEY_PATH = Path("config/key.json")
SCORING_REF_PATH = Path("config/scoring_ref.json")

class OMRApplication:
    """
    Main Controller.
    """
    
    def __init__(self, master: tk.Tk):
        # 1. Load configuration first
        try:
            self.full_config = FileHandler.load_config(CONFIG_PATH)
            self.gui_cfg = self.full_config['GUI_CONFIG']
            self.app_cfg = self.full_config['ALGORITHM_CONFIG']
            
            self.P = self.gui_cfg['PALETTE'] 
            self.S = self.gui_cfg['SIZES_AND_PADDING']
            self.D = self.gui_cfg['DEFAULT_SETTINGS']

            self.all_keys = FileHandler.load_key(KEY_PATH)
            self.scoring_ref = FileHandler.load_scoring_ref(SCORING_REF_PATH)
            
            # Cache danh sách set name
            self.set_names_list = list(self.all_keys.keys())

        except Exception as e:
            messagebox.showerror("Critical Error", f"Lỗi khởi tạo:\n{e}")
            sys.exit(1)

        self.master = master
        self.is_scoring = False
        
        # 2. State Manager
        self.state_manager = FormStateManager(self.all_keys)
        
        # 3. Setup Window Properties
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
        
        s.configure('TCombobox', 
                    font=(default_font_family, input_font_size), 
                    padding=[10, input_pady], 
                    fieldbackground=self.P['C_LIGHT'],
                    foreground=self.P['C_PRIMARY_DARK'],
                    selectbackground=self.P['C_LIGHT'],
                    selectforeground=self.P['C_PRIMARY_DARK']) 

        s.configure('TEntry', 
                    font=(default_font_family, input_font_size), 
                    padding=[10, input_pady], 
                    fieldbackground=self.P['C_LIGHT'],
                    foreground=self.P['C_PRIMARY_DARK'])

        # 4. Init Variables
        self._init_ui_variables()

        # 5. Create Frames
        self.top_controls_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.top_controls_frame.grid(row=0, column=0, sticky='ew')
        
        self.content_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=5)
        self.content_frame.grid(row=1, column=0, sticky='nsew')
        
        self.footer_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.footer_frame.grid(row=2, column=0, sticky='ew')

        # 6. Fill Content
        self._create_top_controls()
        self._refresh_content_area()
        self._create_footer_buttons()
        
        # Thư mục log cha
        self.parent_log_dir = Path("logs")
        self.parent_log_dir.mkdir(exist_ok=True)

    def _init_ui_variables(self):
        self.var_set_name = tk.StringVar(value=self.state_manager.UNSELECTED_SET)
        self.var_test_id = tk.StringVar(value=self.state_manager.UNSELECTED_ID)
        self.var_test_date = tk.StringVar(value=self.state_manager.UNSELECTED_DATE_HINT)

    def _create_top_controls(self):
        """
        Layout Input & Start Button.
        """
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
        self.set_combo = ttk.Combobox(input_area, textvariable=self.var_set_name,
                                     values=self.set_names_list,
                                     state='readonly',
                                     )
        self.set_combo.grid(row=0, column=0, padx=(0, 5), pady=(0, self.S['INPUT_PADY']), sticky='ew')
        
        
        self.id_combo = ttk.Combobox(input_area, textvariable=self.var_test_id,
                                     values=[], 
                                     state='disabled')
        self.id_combo.grid(row=0, column=1, padx=(5, 0), pady=(0, self.S['INPUT_PADY']), sticky='ew') 
        
        # Bind events sau khi tạo xong widget để tránh lỗi Reference
        self.set_combo.bind('<<ComboboxSelected>>', self._on_set_changed)
        self.id_combo.bind('<<ComboboxSelected>>', self._on_id_changed)
        
        # --- HÀNG 1: DATE INPUT ---
        self.date_entry = ttk.Entry(input_area, textvariable=self.var_test_date, width=50) 
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
        self.start_btn = tk.Button(start_button_container, 
                      text="▶", 
                      font=start_button_font, 
                      bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'], 
                      activebackground=self.P['C_PRIMARY_DARK'], 
                      activeforeground=self.P['C_ACCENT'],
                      relief='flat', bd=0, 
                      highlightthickness=0,
                      command=self._on_start_clicked) 
        
        self.start_btn.place(relx=0.5, rely=0.5, anchor='center')
        
        # --- KHU VỰC INFO ---
        info_area = tk.Frame(frame, bg=self.P['C_LIGHT'])
        info_area.grid(row=0, column=1, rowspan=2, sticky='nse') 
        
        tk.Label(info_area, text="TOEIC OMR SCORING v2.0", 
                 font=(self.D['FONT_FAMILY'], 12, "bold"), 
                 fg=self.P['C_PRIMARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')
        
        tk.Label(info_area, text="Refactored & Modularized", 
                 font=(self.D['FONT_FAMILY'], 10), 
                 fg=self.P['C_SECONDARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')

    def _create_footer_buttons(self):

        frame = self.footer_frame
        
        # Căn chỉnh các nút sang phải
        frame.grid_columnconfigure(0, weight=1)
        
        self.view_log_btn = tk.Button(frame, text="View Log", 
                                 font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                                 bg=self.P['C_SECONDARY_DARK'], fg=self.P['C_LIGHT'],
                                 activebackground=self.P['C_PRIMARY_DARK'], 
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, 
                                 padx=15, pady=self.S['ACTION_PADY'],
                                 command=self._on_open_log_folder) 
        self.view_log_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.upload_btn = tk.Button(frame, text="Save & Upload", 
                               font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                               bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                               activebackground=self.P['C_PRIMARY_DARK'],
                               activeforeground=self.P['C_LIGHT'],
                               relief='flat', bd=0, 
                               padx=15, pady=self.S['ACTION_PADY'],
                               state='disabled', 
                               command=self._on_save_clicked)
        self.upload_btn.grid(row=0, column=2, padx=5, pady=5)

    def _refresh_content_area(self, refresh_table_only: bool = False):
        image_files = self.state_manager.get_value('image_files')
        has_files = len(image_files) > 0
        
        # Config bundle để truyền xuống components (giả lập self.P, self.S...)
        config_bundle = {'PALETTE': self.P, 'SIZES_AND_PADDING': self.S, 'DEFAULT_SETTINGS': self.D}

        if refresh_table_only and has_files and hasattr(self, 'table_view'):
            results = self.state_manager.get_value('results')
            self.table_view.update_data(image_files, results)
            return

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if has_files:
            self.table_view = FileTableView(
                self.content_frame,
                on_add=self._on_browse_files,
                on_remove=self._on_remove_files,
                on_clear=self._on_clear_files,
                config=config_bundle
            )
            self.table_view.pack(fill='both', expand=True)
            # Load initial data
            results = self.state_manager.get_value('results')
            self.table_view.update_data(image_files, results)
        else:
            self.drag_area = DragDropArea(
                self.content_frame, 
                on_browse_click=self._on_browse_files,
                config=config_bundle
            )
            self.drag_area.pack(fill='both', expand=True)
            self.table_view = None

    # --- EVENT HANDLERS ---
    def _on_set_changed(self, event):
        # Kiểm tra an toàn
        if not hasattr(self, 'id_combo') or not hasattr(self, 'var_test_id'):
            return

        selected_set = self.set_combo.get() 
        app_logger.debug(f"User selected set: '{selected_set}'")
        
        self.state_manager.set_value('set_name', selected_set)
        
        if selected_set in self.all_keys:
            ids = list(self.all_keys[selected_set].keys())
            self.id_combo.config(values=ids, state='readonly')
            self.var_test_id.set(self.state_manager.UNSELECTED_ID)
            # Reset ID trong state để tránh lưu ID cũ của bộ đề trước
            self.state_manager.set_value('test_id', self.state_manager.UNSELECTED_ID)
        else:
            self.id_combo.config(values=[], state='disabled')

    def _on_id_changed(self, event):
        if not hasattr(self, 'var_test_id'): return
        # Tương tự, lấy trực tiếp từ widget cho chắc chắn
        selected_id = self.id_combo.get()
        self.state_manager.set_value('test_id', selected_id)

    def _on_date_focus_in(self, event):
        if self.var_test_date.get() == self.state_manager.UNSELECTED_DATE_HINT:
            self.var_test_date.set('')

    def _on_date_focus_out(self, event):
        current = self.var_test_date.get()
        if not current.strip():
            self.var_test_date.set(self.state_manager.UNSELECTED_DATE_HINT)
        self.state_manager.set_value('test_date', self.var_test_date.get())

    def _on_browse_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn File Ảnh Bài Làm (.jpg/.jpeg)",
            filetypes=[("JPEG files", "*.jpg;*.jpeg"), ("All Files", "*.*")]
        )
        if files:
            current = self.state_manager.get_value('image_files')
            new_files = [Path(f) for f in files]
            # Simple unique filter
            existing = {f.name for f in current}
            valid = [f for f in new_files if f.name not in existing]
            
            current.extend(valid)
            self.state_manager.set_value('image_files', current)
            self._refresh_content_area()

    def _on_remove_files(self, iids: list):
        to_remove = {Path(iid) for iid in iids}
        current = self.state_manager.get_value('image_files')
        new_list = [f for f in current if f not in to_remove]
        self.state_manager.set_value('image_files', new_list)
        self._refresh_content_area()

    def _on_clear_files(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa tất cả file?"):
            self.state_manager.set_value('image_files', [])
            self.state_manager.set_value('results', []) # Clear cả kết quả cũ
            self._refresh_content_area()

    def _on_start_clicked(self):
        if self.is_scoring: return
        
        self.state_manager.set_value('test_date', self.var_test_date.get())
        is_valid, msg = self.state_manager.validate_and_update_state()
        if not is_valid:
            messagebox.showwarning("Validation Failed", msg)
            return

        self._set_ui_busy(True)
        state = self.state_manager.state
        
        # Logic tạo thư mục (Logic gốc)
        result_name = f"{state['test_date']}_{state['set_name']}_{state['test_id']}".replace(" ", "").replace("-", "")
        self.current_result_dir = self.parent_log_dir / result_name
        self.current_result_dir.mkdir(exist_ok=True)
        
        # Reset results
        self.state_manager.set_value('results', [])
        # Cập nhật UI bảng về trạng thái Pending (Refresh lại bảng)
        self._refresh_content_area(refresh_table_only=True)

        try:
            warp = WarpingProcessor(self.app_cfg)
            omr = OMREngine(self.app_cfg)
            grade = GradeManager(state['key'], self.scoring_ref, state['set_name'], state['test_id'], state['test_date'])
            
            self.worker = ScoringWorker(self, state['image_files'], warp, omr, grade, self.current_result_dir)
            self.worker.start()
        except Exception as e:
            self._set_ui_busy(False)
            messagebox.showerror("Error", f"Lỗi khởi động: {e}")

    def on_file_graded(self, img_path, result_dict, error_msg):
        if hasattr(self, 'table_view') and self.table_view:
            self.table_view.update_single_item(img_path, result_dict, error_msg)
        
        if result_dict:
            res_list = self.state_manager.get_value('results')
            res_list.append(result_dict)

    def on_scoring_complete(self):
        self._set_ui_busy(False)
        messagebox.showinfo("Done", "Đã hoàn tất chấm điểm!")
        if self.state_manager.get_value('results'):
            self.upload_btn.config(state='normal')

    def _set_ui_busy(self, busy):
        self.is_scoring = busy
        state = 'disabled' if busy else 'normal'
        self.start_btn.config(state=state, text="⏳" if busy else "▶")
        self.set_combo.config(state='disabled' if busy else 'readonly')
        self.id_combo.config(state='disabled' if busy else 'readonly')
        
        # Update UI style
        if busy:
            self.start_btn.config(bg=self.P['C_PRIMARY_DARK'], fg=self.P['C_LIGHT'])
        else:
            self.start_btn.config(bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'])

    def _on_open_log_folder(self):
        path = getattr(self, 'current_result_dir', self.parent_log_dir)
        try:
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': os.system(f'open "{path}"')
            else: os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _on_save_clicked(self):
        results = self.state_manager.get_value('results')
        if not results: return
        try:
            path = FileHandler.save_results_to_excel(results, self.current_result_dir)
            if path: messagebox.showinfo("Saved", f"Đã lưu: {path}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))