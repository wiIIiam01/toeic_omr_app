import cv2
import json
import numpy as np
from pathlib import Path
import pandas as pd

def bits_to_char(bits):
    if bits == (0,0,0,0): return '0'
    if bits == (1,0,0,0): return 'A'
    if bits == (0,1,0,0): return 'B'
    if bits == (0,0,1,0): return 'C'
    if bits == (0,0,0,1): return 'D'
    return 'X'

filename = Path("template_config.json")
with open(filename, 'r') as f:
    config = json.load(f)

key_path = Path("key.txt")
result_dir = Path("Result")
result_dir.mkdir(exist_ok=True)
result_xlsx = Path("result.xlsx")
all_results_list = []
excel_columns = ["name", "part1", "part2", "part3", "part4", "part5", "part6", "part7", "answer"]

image_files = list(Path('.').glob('*.jpg'))
for img_path in image_files:
    base_name = img_path.stem
    try:
        img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img_binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(img_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        markers = []
        min_size = 0.5 * config['marker_scaling_ref'] * img_binary.shape[1]
        min_density = 0.7  # tối thiểu 70% pixel trắng trong bounding box
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < min_size or h < min_size:
                continue
            aspect_ratio = w / h
            if not (0.8 <= aspect_ratio <= 1.2):
                continue 
            roi = img_binary[y:y+h, x:x+w]
            density = np.sum(roi==255) / (w*h)
            if density >= min_density:
                markers.append((x, y, w, h))

        if len(markers) >= 4:
            centers = np.array([[x + w//2, y + h//2] for x, y, w, h in markers])
            s = centers.sum(axis=1)
            diff = np.diff(centers, axis=1)

            tl_idx = np.argmin(s)
            br_idx = np.argmax(s)
            tr_idx = np.argmin(diff)
            bl_idx = np.argmax(diff)

            tl_rect = markers[tl_idx]
            tr_rect = markers[tr_idx]
            br_rect = markers[br_idx]
            bl_rect = markers[bl_idx]

            SRC_POINTS = np.float32([
                [tl_rect[0], tl_rect[1]],  # 1. Góc TL của BB TL marker
                [tr_rect[0], tr_rect[1]],  # 2. Góc TL của BB TR marker
                [br_rect[0], br_rect[1]],  # 3. Góc TL của BB BR marker
                [bl_rect[0], bl_rect[1]]   # 4. Góc TL của BB BL marker
            ])
        DST_POINTS = np.float32([
            [0, 0],                                                         # Top-Left
            [config['warp_size']['width'], 0],                              # Top-Right
            [config['warp_size']['width'], config['warp_size']['height']],  # Bottom-Right
            [0, config['warp_size']['height']]                              # Bottom-Left
        ])
        M = cv2.getPerspectiveTransform(SRC_POINTS, DST_POINTS)
        img_warped = cv2.warpPerspective(img_binary, M, (config['warp_size']['width'], config['warp_size']['height']))

        img = cv2.warpPerspective(img, M, (config['warp_size']['width'], config['warp_size']['height']))

        H_new, W_new = img_warped.shape[:2]
        SCAN_THICKNESS = 50 
        X_MIN_SIZE = 19; X_MAX_SIZE = 29  # Kích thước W/H ~ 24 +/- 5
        X_WH_RATIO_MIN = 0.8; X_WH_RATIO_MAX = 1.2 # Tỷ lệ ~ 1
        Y_W_MIN = 22; Y_W_MAX = 32         # Kích thước W ~ 27 +/- 5
        Y_H_MIN = 4; Y_H_MAX = 14  
        valid_contours_top = []
        valid_contours_left = []
        FINAL_X_INDICES = []
        FINAL_Y_INDICES = []

        top_scan_slice = img_warped[0:SCAN_THICKNESS, 0:W_new]
        contours_top, _ = cv2.findContours(top_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours_top:
            x, y, w, h = cv2.boundingRect(c)
            ratio = w / h if h > 0 else 0
            
            if (X_MIN_SIZE <= w <= X_MAX_SIZE and 
                X_MIN_SIZE <= h <= X_MAX_SIZE and
                X_WH_RATIO_MIN <= ratio <= X_WH_RATIO_MAX):
                
                center_x = x + w // 2
                valid_contours_top.append({
                    'center_x': center_x, 
                    'x': x, 
                    'y': y, 
                    'w': w, 
                    'h': h
                })

        if len(valid_contours_top) != 9:
            raise ValueError(f"❌ LỖI TEMPLATE: Biên trên tìm thấy {len(valid_contours_top)} bubble. YÊU CẦU 9.")

        valid_contours_top.sort(key=lambda item: item['center_x'])
        FINAL_X_INDICES = [item['center_x'] for item in valid_contours_top]
        left_scan_slice = img_warped[0:H_new, 0:SCAN_THICKNESS]
        contours_left, _ = cv2.findContours(left_scan_slice, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours_left:
            x, y, w, h = cv2.boundingRect(c)
            
            if (Y_W_MIN <= w <= Y_W_MAX and 
                Y_H_MIN <= h <= Y_H_MAX):
                
                center_y = y + h // 2
                valid_contours_left.append({
                    'center_y': center_y,
                    'x': x, 
                    'y': y, 
                    'w': w, 
                    'h': h
                })
        valid_contours_left.sort(key=lambda item: item['center_y'])
        FINAL_Y_INDICES = [item['center_y'] for item in valid_contours_left]

        bubble_widths = [item['w'] for item in valid_contours_top]
        bubble_heights = [item['h'] for item in valid_contours_top]

        NEW_BUBBLE_W = np.mean(bubble_widths)
        NEW_BUBBLE_H = np.mean(bubble_heights)
        NEW_BUBBLE_R = (NEW_BUBBLE_W + NEW_BUBBLE_H) / 4 

        dash_widths = [item['w'] for item in valid_contours_left]
        dash_heights = [item['h'] for item in valid_contours_left]

        NEW_DASH_W = np.mean(dash_widths)
        NEW_DASH_H = np.mean(dash_heights)

        S = FINAL_X_INDICES 
        U = np.mean([S[5] - S[4], S[3] - S[2], S[2] - S[1]])
        LC = np.mean([(S[6] - S[0]) / 3, S[7] - S[5]])

        JUMP = S[8] - S[1]

        N = []

        N.append((S[1] + S[0]) / 2)

        N.extend([S[1], S[2], S[3]])
        X_1_4 = N[:4] # Lưu trữ x1, x2, x3, x4 để dùng lại

        N.extend([LC + x for x in X_1_4])

        N.extend([S[4], S[5]])

        N.append(N[-1] + U) # x11 = x10 + U
        N.append(N[-1] + U) # x12 = x11 + U

        N.extend([
            S[7] - U,
            S[7],
            S[7] + U,
            S[7] + 2 * U
        ])

        X_1_16 = N[:16]
        N.extend([JUMP + x for x in X_1_16])

        final_reference_grid = []
        for y in FINAL_Y_INDICES:
            row_centers = []
            for x in N:
                row_centers.append((int(x), int(y))) # Chuyển đổi sang int để vẽ
            final_reference_grid.append(row_centers)

        image_with_grid = img.copy() 

        for i, row in enumerate(final_reference_grid):
            for j, (cx, cy) in enumerate(row):
                color_index = j % 4
                
                if color_index == 0: color = (0, 0, 255)    # Đỏ (Red)
                elif color_index == 1: color = (0, 255, 0)  # Xanh Lá (Green)
                elif color_index == 2: color = (255, 0, 0)  # Xanh Dương (Blue)
                else: color = (0, 255, 255)                 # Vàng (Yellow)
                
                cv2.circle(image_with_grid, (cx, cy), int(NEW_BUBBLE_R), color, 1) # Vẽ viền

        FINAL_X_INDICES_32 = N
        PIXEL_INTENSITY_THRESHOLD = 127 
        MIN_FILL_PERCENTAGE = 0.50
        X_CENTERS = FINAL_X_INDICES_32
        Y_CENTERS = FINAL_Y_INDICES
        R = int(NEW_BUBBLE_R) # Bán kính trung bình

        detection_image = img_warped
        def detect_bubble(img_binary, center_x, center_y, R, threshold_value, min_fill_ratio):

            H, W = img_binary.shape[:2]
            
            r_start = max(0, center_y - R)
            r_end = min(H, center_y + R)
            c_start = max(0, center_x - R)
            c_end = min(W, center_x + R)
            
            roi = img_binary[r_start:r_end, c_start:c_end]
            
            if roi.size == 0:
                return 0

            dark_pixels = np.sum(roi >= threshold_value)
            
            total_pixels = roi.size
            fill_ratio = dark_pixels / total_pixels
            
            if fill_ratio >= min_fill_ratio:
                return 1  # Đã tô
            else:
                return 0  # Chưa tô

        result_matrix = np.zeros((len(Y_CENTERS), len(X_CENTERS)), dtype=int)
        marked_circles = [] # Lưu trữ tọa độ của các bubble được tô

        for i, center_y in enumerate(Y_CENTERS): # Lặp qua 25 hàng
            for j, center_x in enumerate(X_CENTERS): # Lặp qua 32 cột
                
                is_marked = detect_bubble(
                    detection_image, 
                    int(center_x), 
                    int(center_y), 
                    R, 
                    PIXEL_INTENSITY_THRESHOLD, 
                    MIN_FILL_PERCENTAGE
                )
                
                result_matrix[i, j] = is_marked
                
                if is_marked == 1:
                    marked_circles.append((int(center_x), int(center_y)))

        MARKER_COLOR = (255, 0, 255) # Màu Magenta (Tím/Hồng đậm) cho bubble đã tô
        FILLED_THICKNESS = -1        # Độ dày -1 để tô đầy hình tròn

        for (cx, cy) in marked_circles:
            cv2.circle(image_with_grid, (cx, cy), R, MARKER_COLOR, FILLED_THICKNESS) 

        OMR_RESULT_MATRIX = result_matrix
        rows, cols = result_matrix.shape

        if rows != len(FINAL_Y_INDICES) or cols != len(FINAL_X_INDICES_32):
            raise ValueError("Kích thước result_matrix không khớp với final indices.")

        if cols % 4 != 0:
            raise ValueError(f"Số cột ({cols}) không chia hết cho 4 — không thể nhóm 4 cột cho mỗi cụm.")

        groups = cols // 4
        num_questions = rows * groups  # kỳ vọng = 200 theo cấu hình của bạn

        answers_list = []

        for g in range(groups):                # g = 0..groups-1
            col_start = g * 4
            col_indices = list(range(col_start, col_start + 4))
            for r in range(rows):              # r = 0..rows-1 (top -> bottom)
                bits = tuple(int(result_matrix[r, c]) for c in col_indices)
                ch = bits_to_char(bits)
                answers_list.append(ch)

        with key_path.open("r", encoding="utf-8") as f:
            key_raw = f.read()
        key = ''.join(key_raw.split())  # remove whitespace/newlines

        n_answers = len(answers_list)
        n_key = len(key)
        if n_key != n_answers:
            raise ValueError(f"Độ dài khác nhau: key.txt có {n_key} ký tự, answers_list có {n_answers} phần tử. Cần bằng nhau.")

        correct_list = [1 if answers_list[i] == key[i] else 0 for i in range(n_answers)]

        ranges_1based = [
            (1, 6),
            (7, 31),
            (32, 70),
            (71, 100),
            (101, 130),
            (131, 146),
            (147, 200)
        ]
        parts = {}
        for idx, (a, b) in enumerate(ranges_1based, start=1):
            s = a - 1
            e = b
            parts[f"part{idx}"] = int(sum(correct_list[s:e]))

        save_img_path = result_dir / f"{base_name}_RESULT.png"
        ok = cv2.imwrite(str(save_img_path), image_with_grid)
        if not ok:
            raise RuntimeError(f"Lưu ảnh thất bại: {save_img_path}")
        answers_string = ''.join(answers_list)

        row_dict = {
            "name": base_name,
            "part1": parts["part1"],
            "part2": parts["part2"],
            "part3": parts["part3"],
            "part4": parts["part4"],
            "part5": parts["part5"],
            "part6": parts["part6"],
            "part7": parts["part7"],
            "answer": answers_string
        }

        all_results_list.append(row_dict)
        print(f"✅ Xử lý thành công: {img_path.name}.")
    except Exception as e:
        print(f"❌ LỖI khi xử lý file {img_path.name}: {e}")
        continue
df = pd.DataFrame(all_results_list, columns=excel_columns)
df.to_excel(result_xlsx, index=False)