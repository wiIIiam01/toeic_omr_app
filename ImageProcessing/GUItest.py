import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
import math

class OMRLayoutDesign:
    # --- PALETTE MÀU ---
    C_PRIMARY_DARK = '#222831'  # Text, main elements, Visible Border
    C_SECONDARY_DARK = '#393E46' # Dark elements, borders, View Log button
    C_ACCENT = '#00ADB5'         # Highlight, START, Save & Upload, Browse buttons
    C_LIGHT = '#EEEEEE'          # Main background
    
    # Khoảng đệm ngang thống nhất cho toàn bộ giao diện
    H_PAD = 20

    # --- KÍCH THƯỚC FONT ---
    INPUT_FONT_SIZE = 20
    ACTION_FONT_SIZE = 12
    
    # Padding đồng nhất cho khoảng thở của Input
    INPUT_PADY = 5 
    
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("TOEIC OMR Scoring")
        master.geometry("720x540") 
        master.configure(bg=self.C_LIGHT)
        
        # Cho phép các hàng và cột chính co giãn
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(1, weight=1) 
        
        # --- THIẾT LẬP STYLE (Cần thiết cho Combobox/Entry) ---
        s = ttk.Style()
        s.theme_use('clam') 
        
        # Cấu hình TCombobox (Màu nền trắng, chữ đen sẫm)
        s.configure('TCombobox', 
                    font=('Arial', self.INPUT_FONT_SIZE), 
                    padding=[10, self.INPUT_PADY],
                    fieldbackground=self.C_LIGHT,
                    foreground=self.C_PRIMARY_DARK,
                    selectbackground=self.C_LIGHT,  # Màu nền khi chọn
                    selectforeground=self.C_PRIMARY_DARK) # Màu chữ khi chọn

        # Cấu hình TEntry (Màu nền trắng, chữ đen sẫm)
        s.configure('TEntry', 
                    font=('Arial', self.INPUT_FONT_SIZE), 
                    padding=[10, self.INPUT_PADY],
                    fieldbackground=self.C_LIGHT,
                    foreground=self.C_PRIMARY_DARK)
        
        # --- 1. BIẾN MÔ PHỎNG ---
        self.selected_set_var = tk.StringVar(master, value="Select Set")
        self.selected_id_var = tk.StringVar(master, value="Select Test") 
        self.test_date_var = tk.StringVar(master)
        # Thiết lập True để xem giao diện bảng (Test Table View)
        self.has_files_loaded = False 

        # --- 2. TẠO CÁC KHUNG (FRAMES) CHÍNH ---
        # Áp dụng H_PAD cho Lề ngang thống nhất
        self.top_controls_frame = tk.Frame(master, bg=self.C_LIGHT, padx=self.H_PAD, pady=10)
        self.top_controls_frame.grid(row=0, column=0, sticky='ew')
        
        self.content_frame = tk.Frame(master, bg=self.C_LIGHT, padx=self.H_PAD, pady=5)
        self.content_frame.grid(row=1, column=0, sticky='nsew')
        
        self.footer_frame = tk.Frame(master, bg=self.C_LIGHT, padx=self.H_PAD, pady=10)
        self.footer_frame.grid(row=2, column=0, sticky='ew')

        # --- 3. ĐIỀN NỘI DUNG VÀO CÁC KHUNG ---
        self._create_top_controls()
        
        if self.has_files_loaded:
            self._create_table_view()
        else:
            self._create_drag_drop_area()
            
        self._create_footer_buttons()

    # Hàm lấy kích thước cố định (chiều rộng và chiều cao) cho nút START (Hình vuông)
    def _get_start_button_size(self):
        # Kích thước cố định 80px
        return 80 

    def _create_top_controls(self):
        frame = self.top_controls_frame
        
        # Đảm bảo tỷ lệ 60/40 luôn được giữ
        frame.grid_columnconfigure(0, weight=6, uniform="top_columns") 
        frame.grid_columnconfigure(1, weight=4, uniform="top_columns") 
        
        # --- 3.1. KHU VỰC INPUT & START (60% WIDTH) ---
        input_and_start_frame = tk.Frame(frame, bg=self.C_LIGHT)
        input_and_start_frame.grid(row=0, column=0, sticky='ew')
        
        # Cấu hình cột: Input Area (Weight 1) | Start Button (Weight 0, Fixed Width)
        input_and_start_frame.grid_columnconfigure(0, weight=1) 
        input_and_start_frame.grid_columnconfigure(1, weight=0) 

        # Khung chứa các input (Set, ID, Date)
        input_area = tk.Frame(input_and_start_frame, bg=self.C_LIGHT)
        input_area.grid(row=0, column=0, rowspan=2, sticky='nsew') 
        
        # Cấu hình 7:3 cho 2 Combobox
        input_area.grid_columnconfigure(0, weight=7, uniform="inputs") 
        input_area.grid_columnconfigure(1, weight=3, uniform="inputs")
        
        # --- HÀNG 0: SET NAME & TEST ID/TEST ---
        self.set_combo = ttk.Combobox(input_area, textvariable=self.selected_set_var,
                                      values=["SET A", "SET B", "SET C", "SET D"], 
                                      state='readonly',
                                      )
        self.set_combo.grid(row=0, column=0, padx=(0, 5), pady=self.INPUT_PADY, sticky='ew')
        
        self.id_combo = ttk.Combobox(input_area, textvariable=self.selected_id_var,
                                     values=[str(i) for i in range(1, 11)], 
                                     state='disabled')
        self.id_combo.grid(row=0, column=1, padx=(5, 0), pady=self.INPUT_PADY, sticky='ew') 

        # --- HÀNG 1: DATE INPUT ---
        self.date_entry = ttk.Entry(input_area, textvariable=self.test_date_var, width=50) 
        self.date_entry.grid(row=1, column=0, columnspan=2, padx=(0, 0), pady=self.INPUT_PADY, sticky='ew')
        self.date_entry.insert(0, "Test Date (DD-MM-YYYY)") 
        
        # --- START BUTTON (Hình vuông, kề sát) ---
        start_size = self._get_start_button_size()
        
        # Khung Container cố định kích thước 80x80px (dùng grid_propagate(False) cho độ tin cậy)
        start_button_container = tk.Frame(input_and_start_frame, bg=self.C_LIGHT,
                                         width=start_size, height=start_size)
        
        # Dùng grid để căn chỉnh. Sticky 'nse' + rowspan=2 để căng chiều cao 2 dòng input.
        start_button_container.grid(row=0, column=1, rowspan=2, padx=(10, 0), pady=0, sticky='nse') 
        start_button_container.grid_propagate(False) # Cưỡng bức kích thước cố định 80x80px

        # Tăng Font size lên 36
        start_button_font = tkfont.Font(family="Arial", size=36, weight="bold")
        
        # Nút START: Tinh chỉnh width=3 và height=1 để đảm bảo hình vuông
        start_btn = tk.Button(start_button_container, 
                  text="▶", 
                  font=start_button_font, 
                  bg=self.C_ACCENT, fg=self.C_PRIMARY_DARK, 
                  activebackground=self.C_PRIMARY_DARK, 
                  activeforeground=self.C_ACCENT,
                  relief='flat', bd=0, 
                  highlightthickness=0,
                  width=3,  # Kích thước cố định theo ký tự
                  height=1, # Giảm chiều cao xuống 1 dòng
                  command=lambda: print("Start Clicked")
                  )
        
        # Căn giữa nút (có kích thước đã điều chỉnh) bên trong container 80x80px
        start_btn.place(relx=0.5, rely=0.5, anchor='center')

        # --- 3.2. KHU VỰC INFO (40% WIDTH, Căn phải) ---
        info_area = tk.Frame(frame, bg=self.C_LIGHT)
        info_area.grid(row=0, column=1, rowspan=2, sticky='nse') 
        
        # Các Label trong khu vực Info sẽ tự động giảm font nếu không gian nhỏ
        tk.Label(info_area, text="TOEIC OMR SCORING v1.0", font=("Arial", 12, "bold"), fg=self.C_PRIMARY_DARK, bg=self.C_LIGHT).pack(anchor='e')
        tk.Label(info_area, text="Developed by [Your Name]", font=("Arial", 10), fg=self.C_SECONDARY_DARK, bg=self.C_LIGHT).pack(anchor='e')
    
    def _create_drag_drop_area(self):
        # --- KHU VỰC DRAG & DROP (Cố định ở trung tâm) ---
        frame = self.content_frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        # drop_area lấp đầy content_frame, loại bỏ viền
        drop_area = tk.Frame(frame, bg=self.C_LIGHT, bd=0) 
        drop_area.grid(row=0, column=0, sticky='nsew') 
        
        # Cấu hình drop_area để căn giữa nội dung bên trong
        drop_area.grid_columnconfigure(0, weight=1)
        
        # Đảm bảo nội dung được căn giữa theo chiều dọc
        # Row 0: Spacer trên (Weight = 1)
        drop_area.grid_rowconfigure(0, weight=1) 
        # Row 4: Spacer dưới (Weight = 1)
        drop_area.grid_rowconfigure(4, weight=1) 
        
        # 1. Placeholder Image (Hình minh họa) - THÊM VIỀN ĐEN
        image_placeholder = tk.Frame(drop_area, width=200, height=150, bg=self.C_LIGHT,
                                     bd=2, relief='solid', 
                                     highlightbackground=self.C_PRIMARY_DARK, 
                                     highlightcolor=self.C_PRIMARY_DARK) 
        
        image_placeholder.grid(row=1, column=0, pady=(10, 0)) 
        image_placeholder.grid_propagate(False) # Cố định kích thước 200x150
        
        # Thiết lập grid cho image_placeholder để căn giữa icon
        image_placeholder.grid_columnconfigure(0, weight=1)
        image_placeholder.grid_rowconfigure(0, weight=1)
        
        # Đảm bảo icon Label được căn giữa tuyệt đối bên trong khung 200x150
        icon_label = tk.Label(image_placeholder, 
                 text="🖼️", 
                 font=("Arial", 60), 
                 fg=self.C_ACCENT, 
                 bg=self.C_LIGHT,
                 justify='center' 
                 )
        # Sử dụng place để đặt label vào chính giữa (relx=0.5, rely=0.5) và căn theo tâm (anchor='center')
        icon_label.place(relx=0.5, rely=0.5, anchor='center')

        # 2. Nút Browse - Màu Accent 
        browse_btn = tk.Button(drop_area, 
                  text="Browse", 
                  font=("Arial", self.ACTION_FONT_SIZE, "bold"),
                  bg=self.C_ACCENT, fg=self.C_PRIMARY_DARK,
                  relief='flat', bd=0, 
                  activebackground=self.C_PRIMARY_DARK, # Hover effect
                  activeforeground=self.C_ACCENT,
                  command=lambda: print("Browse Clicked"))
        browse_btn.grid(row=2, column=0, pady=5, padx=20)

        # 3. Dòng chữ hướng dẫn
        tk.Label(drop_area, 
                 text="or drag a file here", 
                 font=("Arial", 12), 
                 fg=self.C_PRIMARY_DARK, 
                 bg=self.C_LIGHT).grid(row=3, column=0, pady=(0, 10))


    def _create_table_view(self):
        # --- 3.3. BẢNG (TREEVIEW) - Chỉ hiển thị khi self.has_files_loaded = True ---
        frame = self.content_frame
        
        # Khung chứa bảng và scrollbar (lấp đầy content_frame)
        table_container = tk.Frame(frame, bg=self.C_LIGHT)
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
        
        # Nút View Log (Đã chuyển thành tk.Button)
        view_log_btn = tk.Button(frame, text="View Log", 
                                 font=("Arial", self.ACTION_FONT_SIZE, "bold"),
                                 bg=self.C_SECONDARY_DARK, fg=self.C_LIGHT,
                                 activebackground=self.C_PRIMARY_DARK, 
                                 activeforeground=self.C_SECONDARY_DARK,
                                 relief='flat', bd=0, width=15)
        view_log_btn.grid(row=0, column=1, padx=5, pady=5)
        
        # Nút Save & Upload (Accent Color - Đã chuyển thành tk.Button)
        upload_btn = tk.Button(frame, text="Save & Upload", 
                               font=("Arial", self.ACTION_FONT_SIZE, "bold"),
                               bg=self.C_ACCENT, fg=self.C_PRIMARY_DARK,
                               activebackground=self.C_PRIMARY_DARK,
                               activeforeground=self.C_ACCENT,
                               relief='flat', bd=0, width=15)
        upload_btn.grid(row=0, column=2, padx=5, pady=5)


def run_omr_design():
    root = tk.Tk()
    app = OMRLayoutDesign(root)
    root.mainloop()

if __name__ == "__main__":
    run_omr_design()