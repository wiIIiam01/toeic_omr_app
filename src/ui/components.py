import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, List, Dict, Any, Optional
from pathlib import Path

class DragDropArea(tk.Frame):
    """
    Khu vực kéo thả file.
    """
    def __init__(self, parent, on_browse_click: Callable[[], None], config: Dict[str, Any]):
        # Lấy config màu sắc/size
        self.P = config['PALETTE']
        self.S = config['SIZES_AND_PADDING']
        self.D = config['DEFAULT_SETTINGS']
        
        super().__init__(parent, bg=self.P['C_LIGHT'], bd=0)
        self.on_browse_click = on_browse_click
        
        self._setup_ui()

    def _setup_ui(self):
        # Layout gốc từ gui.py
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        self.grid_rowconfigure(4, weight=1) 
        
        # Placeholder Box
        image_placeholder = tk.Frame(self, width=100, height=100, bg=self.P['C_LIGHT'], 
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
        browse_btn = tk.Button(self, 
                      text="Browse", 
                      font=(self.D['FONT_FAMILY'], self.S['ACTION_FONT_SIZE'], "bold"),
                      bg=self.P['C_ACCENT'], fg=self.P['C_PRIMARY_DARK'],
                      relief='flat', bd=0, 
                      activebackground=self.P['C_PRIMARY_DARK'], 
                      activeforeground=self.P['C_LIGHT'],
                      padx=15, pady=self.S['ACTION_PADY'], 
                      command=self.on_browse_click) 
        browse_btn.grid(row=2, column=0, pady=5, padx=20)

        tk.Label(self, 
                 text="or drag a file here", 
                 font=(self.D['FONT_FAMILY'], 12), 
                 fg=self.P['C_PRIMARY_DARK'], 
                 bg=self.P['C_LIGHT']).grid(row=3, column=0, pady=(0, 10))


class FileTableView(tk.Frame):
    """
    Bảng hiển thị danh sách file.
    CODE GỐC: Được trích xuất từ _create_table_view và _resize_treeview_columns trong gui.py
    """
    def __init__(self, parent, 
                 on_add: Callable, on_remove: Callable, on_clear: Callable, 
                 config: Dict[str, Any]):
        
        self.P = config['PALETTE']
        self.S = config['SIZES_AND_PADDING']
        self.D = config['DEFAULT_SETTINGS']
        self.CONF_THRESHOLD = config['conf_threshold']
        
        super().__init__(parent, bg=self.P['C_LIGHT'])
        
        self.on_add = on_add
        self.on_remove = on_remove
        self.on_clear = on_clear
        
        self.data_map = {}
        self.on_row_click = None
        
        self.tree: Optional[ttk.Treeview] = None
        self._setup_ui()
        self.tree.bind("<Double-1>", self._on_double_click)
        
        # Bind sự kiện resize để tính toán cột y như logic cũ
        self.bind("<Configure>", self._resize_treeview_columns)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        style = ttk.Style()
        style.configure("Treeview", 
                        background=self.P['C_LIGHT'],
                        fieldbackground=self.P['C_LIGHT'],
                        foreground="black")
        
        # Cấu hình màu khi chọn (Selected)
        style.map('Treeview', 
                  background=[('selected', self.P['C_SECONDARY_DARK'])],
                  foreground=[('selected', 'white')])
        
        # Khung chứa Bảng và các nút quản lý file
        table_and_controls_frame = tk.Frame(self, bg=self.P['C_LIGHT'])
        table_and_controls_frame.grid(row=0, column=0, sticky='nsew')
        
        table_and_controls_frame.grid_columnconfigure(0, weight=1)
        table_and_controls_frame.grid_rowconfigure(0, weight=1) # Dành cho Treeview

        # --- NÚT QUẢN LÝ FILE (HÀNG 1) ---
        file_management_frame = tk.Frame(table_and_controls_frame, bg=self.P['C_LIGHT'])
        file_management_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
        
        file_management_frame.grid_columnconfigure(0, weight=1) 
        
        # Nút Add
        self.add_btn = tk.Button(file_management_frame, text="Add", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self.on_add) 
        self.add_btn.grid(row=0, column=1, padx=0, pady=0)
        
        # Nút Remove
        self.remove_btn = tk.Button(file_management_frame, text="Remove", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self._internal_remove) 
        self.remove_btn.grid(row=0, column=2, padx=0, pady=0)
        
        # Nút Clear
        self.clear_btn = tk.Button(file_management_frame, text="Clear", 
                                 font=(self.D['FONT_FAMILY'], 9),
                                 bg=self.P['C_LIGHT'], fg=self.P['C_SECONDARY_DARK'],
                                 activeforeground=self.P['C_ACCENT'],
                                 relief='flat', bd=0, padx=10, pady=self.S['ACTION_PADY'],
                                 command=self.on_clear) 
        self.clear_btn.grid(row=0, column=3, padx=0, pady=0)

        # --- BẢNG (TREEVIEW) (HÀNG 0) ---
        table_container = tk.Frame(table_and_controls_frame, bg=self.P['C_LIGHT'])
        table_container.grid(row=0, column=0, sticky='nsew')
        
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        scrollbar_y = ttk.Scrollbar(table_container, orient="vertical")
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        
        columns = ("name", "total_score", "lc_score", "rc_score", "confidence", "status")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", 
                                 yscrollcommand=scrollbar_y.set, selectmode='extended')
        scrollbar_y.config(command=self.tree.yview)
        
        self.tree.heading("name", text="Name", anchor='center')
        self.tree.heading("total_score", text="Total", anchor='center')
        self.tree.heading("lc_score", text="LC", anchor='center')
        self.tree.heading("rc_score", text="RC", anchor='center')
        self.tree.heading("confidence", text="Conf.", anchor='center')
        self.tree.heading("status", text="Status", anchor='center')
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        
        self.tree.tag_configure('warning', background='#EFE3D3', foreground='#393E46')
        self.tree.tag_configure('success', foreground=self.P['C_SECONDARY_DARK']) 
        self.tree.tag_configure('failed', foreground='red')

    def _resize_treeview_columns(self, event=None):
        """
        Logic co giãn cột.
        """
        if self.tree is None: return

        # Lấy chiều rộng hiện tại của widget frame này
        # Trừ đi khoảng padding nếu cần, ở đây lấy width của container
        total_width = self.winfo_width() - (self.S['H_PAD'] * 2) - 20
        
        if total_width < 100: return 

        # Tỉ lệ chiều dài cột (4:1.5:1:1:2.5, Tổng = 10)
        ratios = {
            "name": 4.0, "total_score": 1.2,
            "lc_score": 0.75, "rc_score": 0.75,
            "confidence": 0.8, "status": 2.5,
        }
        
        total_ratio = sum(ratios.values())
        
        for col_id, ratio in ratios.items():
            new_width = int(total_width * ratio / total_ratio)
            self.tree.column(col_id, width=new_width, minwidth=20) 
        
        # Điều chỉnh cột "name" để nó co giãn
        self.tree.column("name", stretch=tk.YES)
        
    def _on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id and self.on_row_click:
            self.on_row_click(item_id)

    def update_data(self, image_files: List[Path], results_list: List[Dict]):
        """Cập nhật dữ liệu bảng."""
        # Xóa cũ
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Tạo map kết quả để tra cứu nhanh theo tên file
        results_map = {res['Name']: res for res in results_list}

        for img_path in image_files:
            file_name = img_path.name
            base_name = img_path.stem
            iid = str(img_path)
            
            if base_name in results_map:
                res = results_map[base_name]
                self.data_map[str(img_path)] = res
                avg_conf = res.get('Confidence', 0.0)
                min_conf = res.get('LowestConf', 0.0)
                is_reviewed = res.get('is_reviewed', False)
                
                if is_reviewed:
                    status = "✅ Done"
                    tag = 'success'
                elif min_conf < self.CONF_THRESHOLD:
                    status = "⚠️ Review Needed"
                    tag = 'warning'
                else:
                    status = "✅ Done"
                    tag = 'success'
                    
                conf_str = f"{int(avg_conf * 100)}%"
                
                val = (file_name, res['Total'], res['LC'], res['RC'], conf_str, status)
                self.tree.insert("", "end", iid=iid, values=val, tags = (tag,))
            else:
                val = (file_name, "-", "-", "-", "-", "Pending")
                self.tree.insert("", "end", iid=iid, values=val)

    def update_single_item(self, img_path: Path, result_dict: Optional[Dict], error_msg: Optional[str]):
        """Cập nhật 1 dòng (dùng khi worker chấm xong)."""
        iid = str(img_path)
        if not self.tree.exists(iid): return
        
        if result_dict:
            avg_conf = result_dict.get('Confidence', 0.0)
            min_conf = result_dict.get('LowestConf', 0.0)
            is_reviewed = result_dict.get('is_reviewed', False)
            
            if is_reviewed:
                status = "✅ Done"
                tag = 'success'
            elif min_conf < self.CONF_THRESHOLD:
                status = "⚠️ Review Needed"
                tag = 'warning'
            else:
                status = "✅ Done"
                tag = 'success'
                
            values = (
                img_path.name, 
                result_dict['Total'], 
                result_dict['LC'],
                result_dict['RC'],
                f"{int(avg_conf * 100)}%",
                status
            )
            self.data_map[iid] = result_dict
            self.tree.item(iid, values=values)
            self.tree.item(iid, tags=(tag,))
        else:
            values = (img_path.name, "-", "-", "-", "-", f"❌ Failed: {error_msg}")
            self.tree.item(iid, values=values)
            self.tree.item(iid, tags=('failed',))
            
    def get_item_data(self, iid):
        return self.data_map.get(iid)

    def _internal_remove(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất một file để xóa.")
            return
        self.on_remove(list(selected_iids))