import os
import glob
import shutil
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

# ==========================================
# 1. CẤU HÌNH ĐƯỜNG DẪN DỰ ÁN
# ==========================================
# BASE_DIR là thư mục 'labeling'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CONFLICT_DIR lùi lại 1 cấp để vào thư mục 'conflict' (nằm ở ROOT)
CONFLICT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'conflict'))

# Tạo sẵn 3 folder đích trực tiếp trong thư mục conflict
DEST_FOLDERS = ['Selected', 'Deselected', 'Empty']
for folder in DEST_FOLDERS:
    os.makedirs(os.path.join(CONFLICT_DIR, folder), exist_ok=True)

# ==========================================
# 2. LOGIC GOM NHÓM ẢNH (LABELING TAB)
# ==========================================
def get_grouped_questions():
    # Quét tất cả file png nằm trong 4 thư mục con conf_xx_xx
    search_pattern = os.path.join(CONFLICT_DIR, "conf_*", "*.png")
    files = glob.glob(search_pattern)
    
    base_groups = defaultdict(lambda: defaultdict(list))
    
    for f in files:
        basename = os.path.basename(f)
        parts = basename.replace('.png', '').split('_')
        if len(parts) < 4: 
            continue
            
        q_idx, opt, conf, timestamp = parts[0], parts[1], parts[2], int(parts[3])
        base_groups[(q_idx, conf)][opt].append((timestamp, f))
        
    final_groups = []
    for (q_idx, conf), opts_dict in base_groups.items():
        list_A = sorted(opts_dict.get('OptA', []))
        list_B = sorted(opts_dict.get('OptB', []))
        list_C = sorted(opts_dict.get('OptC', []))
        list_D = sorted(opts_dict.get('OptD', []))
        
        min_len = min(len(list_A), len(list_B), len(list_C), len(list_D))
        for i in range(min_len):
            final_groups.append({
                'id': f"{q_idx}_{conf}_{list_A[i][0]}",
                'q_index': q_idx,
                'confidence': conf.replace('conf', ''),
                'A': list_A[i][1], 'B': list_B[i][1], 'C': list_C[i][1], 'D': list_D[i][1]
            })
            
    final_groups.sort(key=lambda x: int(x['q_index'].replace('Q', '')))
    return final_groups

# ==========================================
# 3. DANH SÁCH API (ROUTES)
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasks')
def get_tasks():
    return jsonify(get_grouped_questions())

@app.route('/api/image')
def serve_image():
    path = request.args.get('path')
    return send_file(path)

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    paths = data['paths']
    labels = data['labels']
    
    opts = ['A', 'B', 'C', 'D']
    for i in range(4):
        label = labels[i]
        src_path = paths[opts[i]]
        
        if label is None: continue 
            
        filename = os.path.basename(src_path)
        dest_path = os.path.join(CONFLICT_DIR, label, filename)
        
        try:
            shutil.move(src_path, dest_path)
        except Exception as e:
            print(f"Lỗi di chuyển file {filename}: {e}")
            
    return jsonify({"status": "success"})

# --- 2 API DÀNH CHO TAB REVIEW (GRID) ---

@app.route('/api/labeled/<label>')
def get_labeled_images(label):
    if label not in DEST_FOLDERS:
        return jsonify([])
    folder_path = os.path.join(CONFLICT_DIR, label)
    
    # Lấy tất cả ảnh png trong thư mục nhãn (Selected/Deselected/Empty)
    files = glob.glob(os.path.join(folder_path, "*.png"))
    
    # Sắp xếp ảnh mới xử lý lên đầu tiên
    files.sort(key=os.path.getmtime, reverse=True)
    return jsonify(files)

@app.route('/api/relabel', methods=['POST'])
def relabel():
    try:
        # force=True ép Flask đọc JSON kể cả khi header bị thiếu
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Không nhận được dữ liệu JSON từ trình duyệt"}), 400
            
        src_path = data.get('path')
        new_label = data.get('new_label')
        
        if not src_path or not new_label:
            return jsonify({"error": "Thiếu dữ liệu path hoặc new_label"}), 400
            
        if new_label not in DEST_FOLDERS:
            return jsonify({"error": "Nhãn không hợp lệ"}), 400
            
        filename = os.path.basename(src_path)
        dest_path = os.path.join(CONFLICT_DIR, new_label, filename)
        
        shutil.move(src_path, dest_path)
        return jsonify({"status": "success"})
        
    except Exception as e:
        import traceback
        traceback.print_exc() # In lỗi chi tiết ra cửa sổ CMD màu đen
        return jsonify({"error": f"Lỗi Python: {str(e)}"}), 500
# ==========================================
# 4. CHẠY SERVER
# ==========================================
if __name__ == '__main__':
    print(f"Đang chạy Labeling Tool...")
    print(f"Thư mục gốc xử lý: {CONFLICT_DIR}")
    # Đảm bảo các hàm app.route phải nằm TRƯỚC dòng app.run này
    app.run(debug=False, port=5000)