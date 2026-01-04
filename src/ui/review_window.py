import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pathlib import Path
from src.utils import FileHandler

CONFIG_PATH = Path("config/app_config.json")

class ReviewWindow(tk.Toplevel):
    def __init__(self, parent, student_name, img_path, current_answers, confidence_list, on_save_callback):
        """
        Args:
            parent: Cửa sổ cha (AppWindow)
            student_name: Tên học viên
            img_path: Đường dẫn đến ảnh kết quả (đã vẽ ô vuông)
            current_answers: Chuỗi đáp án hiện tại (VD: "ABCD0A...")
            confidence_list: List độ tự tin tương ứng (VD: [0.99, 0.15, ...])
            on_save_callback: Hàm sẽ gọi khi người dùng bấm Save (trả về chuỗi đáp án mới)
        """
        super().__init__(parent)
        self.title(f"Review: {student_name}")
        self.config = FileHandler.load_config(CONFIG_PATH)
        self.gui_cfg = self.config['GUI_CONFIG']
        self.app_cfg = self.config['ALGORITHM_CONFIG']
        
        self.P = self.gui_cfg['PALETTE'] 
        self.D = self.gui_cfg['DEFAULT_SETTINGS']
            
        self.geometry(self.D['REVIEW_GEOMETRY'])
        
        # Data
        self.img_path = Path(img_path)
        self.answers = list(current_answers)
        self.confidences = confidence_list
        self.on_save = on_save_callback
        
        self.CONF_THRESHOLD = self.app_cfg['conf_threshold']
        
        # UI Setup
        self._setup_layout()
        self._load_image()
        self._load_low_conf_questions()
        
        # Chặn tương tác với cửa sổ chính khi đang review (Modal mode)
        self.grab_set()

    def _setup_layout(self):
        self.main_container = tk.Frame(self)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.frame_control = tk.Frame(self.main_container, width=180, bg=self.P['C_LIGHT'])
        self.frame_control.pack(side=tk.RIGHT, fill=tk.Y)
        self.frame_control.pack_propagate(False)
        
        # --- CỘT TRÁI: ẢNH ---
        self.frame_img = ttk.Frame(self.main_container, borderwidth=2, relief="sunken")
        self.frame_img.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.frame_img, bg=self.P['C_PRIMARY_DARK'], highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        
        # Header
        lbl_header = tk.Label(self.frame_control, text="REVIEW",
                              font=("Arial", 12, "bold"),
                              bg=self.P['C_LIGHT'])
        lbl_header.pack(pady=10)
        
        # Vùng chứa list câu hỏi
        self.list_container = tk.Frame(self.frame_control, bg=self.P['C_LIGHT'])
        self.list_container.pack(fill=tk.BOTH, expand=True, padx=2)
        
        self.style = ttk.Style()
        self.style.configure('Review.TCombobox', 
                             fieldbackground=self.P['C_LIGHT'], # Màu nền ô nhập
                             background=self.P['C_LIGHT'])      # Màu nền mũi tên
        # Map cho trạng thái readonly (quan trọng)
        self.style.map('Review.TCombobox', 
                       fieldbackground=[('readonly', self.P['C_LIGHT'])],
                       selectbackground=[('readonly', self.P['C_LIGHT'])])
        
        # Footer buttons
        btn_frame = tk.Frame(self.frame_control, bg=self.P['C_LIGHT'])
        btn_frame.pack(fill=tk.X, pady=5, padx=5)
        
        btn_save = tk.Button(btn_frame, text="Save", 
                             bg=self.P['C_ACCENT'],
                             fg=self.P['C_PRIMARY_DARK'],       
                             font=("Arial", 11, "bold"),
                             relief='flat',
                             padx=20, pady=4,
                             activebackground=self.P['C_PRIMARY_DARK'],
                             activeforeground=self.P['C_LIGHT'],
                             command=self._save_changes)
        btn_save.pack(side=tk.RIGHT)
        
        btn_cancel = tk.Button(btn_frame, text="Cancel", 
                               bg=self.P['C_SECONDARY_DARK'],
                               fg=self.P['C_LIGHT'], 
                               font=("Arial", 11, "bold"),
                               relief='flat', 
                               padx=20, pady=4,
                               activebackground=self.P['C_PRIMARY_DARK'],
                               activeforeground=self.P['C_ACCENT'],
                               command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=5)


    def _load_image(self):
        """Load ảnh từ đường dẫn"""
        if not self.img_path.exists():
            messagebox.showerror("Lỗi", f"Không tìm thấy ảnh: {self.img_path}")
            return
            
        try:
            # Dùng PIL để mở ảnh
            pil_img = Image.open(self.img_path)
            w, h = pil_img.size
            pil_img = pil_img.crop((80, 140, w, h))
            
            new_w, new_h = pil_img.size
            final_w = int(new_w * 0.9)
            final_h = int(new_h * 0.9)
            
            # Dùng LANCZOS để ảnh sắc nét nhất khi thu nhỏ
            pil_img = pil_img.resize((final_w, final_h), Image.Resampling.LANCZOS)

            self.tk_img = ImageTk.PhotoImage(pil_img)
            self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            
        except Exception as e:
            messagebox.showerror("Lỗi ảnh", str(e))

    def _load_low_conf_questions(self):
        """Tạo các widget sửa bài cho câu có confidence thấp"""
        row_idx = 0
        count = 0
        
        # Duyệt qua tất cả câu hỏi
        for i, (ans, conf) in enumerate(zip(self.answers, self.confidences)):
            # Chỉ hiện những câu Confidence < Threshold
            if conf < self.CONF_THRESHOLD or (ans == '0' and conf < self.CONF_THRESHOLD*2):
                self._create_question_row(i, ans, conf, row_idx)
                row_idx += 1
                count += 1
        
        if count == 0:
            tk.Label(self.list_container, text="Nothing to review!",
                      foreground="green",
                      bg=self.P['C_LIGHT']
                      ).pack(pady=20)

    def _create_question_row(self, q_index, ans, conf, row_idx):
        f = tk.Frame(self.list_container, bg=self.P['C_LIGHT'])
        f.pack(fill=tk.X, pady=1, padx=1)
        
        lbl_text = f"Question {q_index + 1}"
        
        tk.Label(f, text=lbl_text, width=13,
                        foreground='black',
                        bg=self.P['C_LIGHT'],
                        font=("Arial", 10),
                        anchor='w'
                        ).pack(side=tk.LEFT, padx=(0,2))
        
        # Combobox chọn đáp án
        cbo = ttk.Combobox(f, values=['A', 'B', 'C', 'D', '0'], width=3, state="readonly", style='Review.TCombobox')
        cbo.set(ans) # Set giá trị hiện tại
        cbo.pack(side=tk.LEFT, padx=0)
        
        # Bind sự kiện: Khi chọn xong thì update vào list self.answers
        # Lưu ý dùng closure lambda x=q_index để bắt cứng giá trị index
        cbo.bind("<<ComboboxSelected>>", lambda event, idx=q_index: self._on_answer_changed(idx, cbo.get()))

    def _on_answer_changed(self, index, new_value):
        """Cập nhật list đáp án trong bộ nhớ"""
        self.answers[index] = new_value
       

    def _save_changes(self):
        """Gửi chuỗi đáp án mới về App để chấm lại"""
        new_answers_str = "".join(self.answers)
        
        if self.on_save:
            # Callback này sẽ gọi hàm tính lại điểm bên AppWindow
            self.on_save(new_answers_str)
            
        self.destroy()