import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont, messagebox
import json
import os
import sys
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import threading
from typing import Dict, Any, List

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
        
        # --- 1. BIẾN MÔ PHỎNG ---
        self.selected_set_var = tk.StringVar(master, value="Select Set")
        self.selected_id_var = tk.StringVar(master, value="Test") 
        self.test_date_var = tk.StringVar(master)
        self.has_files_loaded = False 

        # --- 2. TẠO CÁC KHUNG (FRAMES) CHÍNH ---
        self.top_controls_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.top_controls_frame.grid(row=0, column=0, sticky='ew')
        
        self.content_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=5)
        self.content_frame.grid(row=1, column=0, sticky='nsew')
        
        self.footer_frame = tk.Frame(master, bg=self.P['C_LIGHT'], padx=self.S['H_PAD'], pady=10)
        self.footer_frame.grid(row=2, column=0, sticky='ew')

        # --- 3. ĐIỀN NỘI DUNG VÀO CÁC KHUNG ---
        self._create_top_controls()
        
        if self.has_files_loaded:
            self._create_table_view()
        else:
            self._create_drag_drop_area()
            
        self._create_footer_buttons()

    def _load_config(self, filename='GUI_config.json'):
        default_config = {
            "PALETTE": {"C_PRIMARY_DARK": '#222831', "C_SECONDARY_DARK": '#393E46', "C_ACCENT": '#00ADB5', "C_LIGHT": '#EEEEEE'},
            "SIZES_AND_PADDING": {"H_PAD": 20, "INPUT_FONT_SIZE": 20, "ACTION_FONT_SIZE": 11, "INPUT_PADY": 5, "ACTION_PADY": 5},
            "DEFAULT_SETTINGS": {"FONT_FAMILY": "Arial", "WINDOW_TITLE": "TOEIC OMR Scoring (Mặc Định)", "GEOMETRY": "720x540"}
        }
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Lỗi: Không tìm thấy file cấu hình {filename}. Sử dụng cấu hình mặc định.")
            return default_config
        except json.JSONDecodeError:
            print(f"Lỗi: File cấu hình {filename} không hợp lệ. Sử dụng cấu hình mặc định.")
            return default_config

    def _create_top_controls(self):
        frame = self.top_controls_frame
        
        frame.grid_columnconfigure(0, weight=6, uniform="top_columns") 
        frame.grid_columnconfigure(1, weight=4, uniform="top_columns") 
        
        # --- 3.1. KHU VỰC INPUT & START (60% WIDTH) ---
        input_and_start_frame = tk.Frame(frame, bg=self.P['C_LIGHT'])
        input_and_start_frame.grid(row=0, column=0, sticky='ew')
        
        input_and_start_frame.grid_columnconfigure(0, weight=1) 
        input_and_start_frame.grid_columnconfigure(1, weight=0, minsize=80) 

        # Khung chứa các input (Set, ID, Date)
        input_area = tk.Frame(input_and_start_frame, bg=self.P['C_LIGHT'])
        input_area.grid(row=0, column=0, rowspan=2, sticky='nsew') 
        
        # Cấu hình 7:3 cho 2 Combobox
        input_area.grid_columnconfigure(0, weight=7, uniform="inputs") 
        input_area.grid_columnconfigure(1, weight=3, uniform="inputs")
        
        # --- HÀNG 0: SET NAME & TEST ID/TEST ---
        self.set_combo = ttk.Combobox(input_area, textvariable=self.selected_set_var,
                                      values=["SET A", "SET B", "SET C", "SET D"], 
                                      state='readonly',
                                      )
        self.set_combo.grid(row=0, column=0, padx=(0, 5), pady=(0, self.S['INPUT_PADY']), sticky='ew')
        
        self.id_combo = ttk.Combobox(input_area, textvariable=self.selected_id_var,
                                     values=[str(i) for i in range(1, 11)], 
                                     state='disabled')
        self.id_combo.grid(row=0, column=1, padx=(5, 0), pady=(0, self.S['INPUT_PADY']), sticky='ew') 

        # --- HÀNG 1: DATE INPUT ---
        self.date_entry = ttk.Entry(input_area, textvariable=self.test_date_var, width=50) 
        self.date_entry.grid(row=1, column=0, columnspan=2, padx=(0, 0), 
                             pady=(self.S['INPUT_PADY'], 0), sticky='ew')
        self.date_entry.insert(0, "Test Date (DD-MM-YYYY)") 
        
        # --- START BUTTON (Hình vuông, kề sát) ---
        start_button_container = tk.Frame(input_and_start_frame, bg=self.P['C_LIGHT'])
        start_button_container.grid(row=0, column=1, rowspan=2, padx=(10, 0), pady=0, sticky='nsew') 
        
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
                  width=3,  
                  command=lambda: print("Start Clicked")
                  )
        
        start_btn.place(relx=0.5, rely=0.5, anchor='center')

        # --- 3.2. KHU VỰC INFO (40% WIDTH, Căn phải) ---
        info_area = tk.Frame(frame, bg=self.P['C_LIGHT'])
        info_area.grid(row=0, column=1, rowspan=2, sticky='nse') 
        
        tk.Label(info_area, text="TOEIC OMR SCORING v1.0", 
                 font=(self.D['FONT_FAMILY'], 12, "bold"), 
                 fg=self.P['C_PRIMARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')
        
        tk.Label(info_area, text="Developed by Phong Nguyen", 
                 font=(self.D['FONT_FAMILY'], 10), 
                 fg=self.P['C_SECONDARY_DARK'], bg=self.P['C_LIGHT']).pack(anchor='e')
    
    def _create_drag_drop_area(self):
        # --- KHU VỰC DRAG & DROP (Cố định ở trung tâm) ---
        frame = self.content_frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        drop_area = tk.Frame(frame, bg=self.P['C_LIGHT'], bd=0) 
        drop_area.grid(row=0, column=0, sticky='nsew') 
        
        drop_area.grid_columnconfigure(0, weight=1)
        drop_area.grid_rowconfigure(0, weight=1) 
        drop_area.grid_rowconfigure(4, weight=1) 
        
        # 1. Placeholder Image
        image_placeholder = tk.Frame(drop_area, width=100, height=100, bg=self.P['C_LIGHT'], 
                                     highlightbackground=self.P['C_PRIMARY_DARK'], 
                                     highlightcolor=self.P['C_PRIMARY_DARK']) 
        
        image_placeholder.grid(row=1, column=0, pady=(10, 0)) 
        image_placeholder.grid_propagate(False) 

        image_placeholder.grid_columnconfigure(0, weight=1)
        image_placeholder.grid_rowconfigure(0, weight=1)
        
        icon_label = tk.Label(image_placeholder, 
                 text="     🖼️", 
                 font=(self.D['FONT_FAMILY'], 60), 
                 fg=self.P['C_ACCENT'], 
                 bg=self.P['C_LIGHT']
                 )
        icon_label.grid(row=0, column=0)

        # 2. Nút Browse 
        browse_btn = tk.Button(drop_area, 
                  text="Browse", 
                  font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                  bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                  relief='flat', bd=0, 
                  activebackground=self.P['C_PRIMARY_DARK'], 
                  activeforeground=self.P['C_ACCENT'],
                  padx=15, pady=self.S['ACTION_PADY'], 
                  command=lambda: print("Browse Clicked"))
        browse_btn.grid(row=2, column=0, pady=5, padx=20)

        # 3. Dòng chữ hướng dẫn
        tk.Label(drop_area, 
                 text="or drag a file here", 
                 font=(self.D['FONT_FAMILY'], 12), 
                 fg=self.P['C_PRIMARY_DARK'], 
                 bg=self.P['C_LIGHT']).grid(row=3, column=0, pady=(0, 10))


    def _create_table_view(self):
        # --- 3.3. BẢNG (TREEVIEW) - Chỉ hiển thị khi self.has_files_loaded = True ---
        frame = self.content_frame
        
        table_container = tk.Frame(frame, bg=self.P['C_LIGHT'])
        table_container.grid(row=0, column=0, sticky='nsew')
        
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        # Tạo Scrollbar dọc
        scrollbar_y = ttk.Scrollbar(table_container, orient="vertical")
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        
        columns = ("name", "col2", "col3", "col4", "status")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", yscrollcommand=scrollbar_y.set)
        scrollbar_y.config(command=self.tree.yview)
        
        # Thiết lập Tỉ lệ chiều dài cột (4:1.5:1:1:2.5, Tổng = 10)
        total_width = 960 
        col_widths = {
            "name": int(total_width * 4.0 / 10.0), "col2": int(total_width * 1.5 / 10.0),
            "col3": int(total_width * 1.0 / 10.0), "col4": int(total_width * 1.0 / 10.0),
            "status": int(total_width * 2.5 / 10.0),
        }
        
        self.tree.heading("name", text="Image File Name", anchor='w')
        self.tree.column("name", width=col_widths["name"], minwidth=50, stretch=tk.YES)
        
        self.tree.heading("col2", text="Col 2", anchor='center')
        self.tree.column("col2", width=col_widths["col2"], minwidth=50, stretch=tk.NO)
        
        self.tree.heading("col3", text="Col 3", anchor='center')
        self.tree.column("col3", width=col_widths["col3"], minwidth=50, stretch=tk.NO)
        
        self.tree.heading("col4", text="Col 4", anchor='center')
        self.tree.column("col4", width=col_widths["col4"], minwidth=50, stretch=tk.NO)
        
        self.tree.heading("status", text="Status", anchor='center')
        self.tree.column("status", width=col_widths["status"], minwidth=50, stretch=tk.NO)
        
        mock_data = [
            ("bai_lam_001.jpg", 1, 2, 3, "Done"),
            ("bai_lam_002.jpg", 4, 5, 6, "Pending"),
            ("bai_lam_003_error.jpg", 0, 0, 0, "Raise Error"),
        ]
        for item in mock_data:
            self.tree.insert("", "end", values=item)

        self.tree.grid(row=0, column=0, sticky='nsew')


    def _create_footer_buttons(self):
        # --- 3.4. FOOTER BUTTONS (BOTTOM RIGHT) ---
        frame = self.footer_frame
        
        # Căn chỉnh các nút sang phải
        frame.grid_columnconfigure(0, weight=1)
        
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
        upload_btn = tk.Button(frame, text="Save & Upload", 
                               font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                               bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                               activebackground=self.P['C_PRIMARY_DARK'],
                               activeforeground=self.P['C_ACCENT'],
                               relief='flat', bd=0, 
                               padx=15, pady=self.S['ACTION_PADY']) 
        upload_btn.grid(row=0, column=2, padx=5, pady=5)


def run_omr_design():
    root = tk.Tk()
    app = OMRLayoutDesign(root)
    root.mainloop()

if __name__ == "__main__":
    run_omr_design()