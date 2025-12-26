import os
from PIL import Image
from pathlib import Path

def process_rotation():
    # 1. Lấy thư mục hiện tại đang chứa file code
    current_dir = Path.cwd()
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    
    # 2. Giao diện nhập liệu nhanh
    print("=== CÔNG CỤ XOAY ẢNH NHANH CHO OMR ===")
    print(f"Thư mục hiện tại: {current_dir}")
    print("-" * 40)
    print("Chọn góc muốn xoay (Xoay thực tế vào điểm ảnh):")
    print("1. Xoay 90 độ (Cùng chiều kim đồng hồ)")
    print("2. Xoay 180 độ")
    print("3. Xoay 270 độ (Tương đương 'Rotate Left' của Windows)")
    
    choice = input("\nNhập số thứ tự (1/2/3): ").strip()
    
    mapping = {
        "1": (90, Image.ROTATE_270),
        "2": (180, Image.ROTATE_180),
        "3": (270, Image.ROTATE_90)
    }
    
    if choice not in mapping:
        print("Lựa chọn không hợp lệ. Vui lòng chạy lại!")
        return

    angle_name, pil_transpose = mapping[choice]
    
    # 3. Tạo thư mục output: ví dụ "rotated_270"
    output_folder = current_dir / f"rotated_{angle_name}"
    output_folder.mkdir(exist_ok=True)
    
    # 4. Xử lý ảnh
    print(f"\nĐang xử lý ảnh và lưu vào: {output_folder.name}...")
    
    count = 0
    for file_path in current_dir.iterdir():
        # Kiểm tra định dạng ảnh và tránh xử lý file code/thư mục output
        if file_path.suffix.lower() in valid_extensions and file_path.is_file():
            try:
                with Image.open(file_path) as img:
                    # Xoay cứng vào pixel
                    rotated_img = img.transpose(pil_transpose)
                    
                    # Lưu ảnh mới, loại bỏ EXIF cũ để OMR không bị đọc sai lần nữa
                    rotated_img.save(output_folder / file_path.name, quality=95, subsampling=0)
                    
                    count += 1
                    print(f"Successfully: {file_path.name}")
            except Exception as e:
                print(f"Error {file_path.name}: {e}")

    print("-" * 40)
    print(f"HOÀN TẤT! Đã xử lý {count} ảnh.")
    input("Nhấn Enter để thoát...")

if __name__ == "__main__":
    process_rotation()