# TOEIC OMR SCORING - PHẦN MỀM CHẤM ĐIỂM PHIẾU TRẮC NGHIỆM TỰ ĐỘNG
**Môn học:** Lập Trình Python Cho Học Máy
**Sinh viên:** Nguyễn Văn Phong - 66132804
**Ngành:** Khoa Học Máy Tính (CS)
**Hướng dẫn:** Ts. Phạm Văn Nam
---

## 1. Giới thiệu
Ứng dụng chấm thi trắc nghiệm tự động sử dụng công nghệ Xử lý ảnh (Computer Vision) để nhận diện phiếu trả lời, tự động so khớp đáp án và quản lý điểm số. Dự án được thiết kế theo kiến trúc Modulization, tách biệt rõ ràng giữa logic xử lý (Core), giao diện (UI) và dữ liệu (Config/Logs).

## 2. Tính năng nổi bật
* **Xử lý ảnh:** Tự động căn chỉnh phiếu thi và nhận diện vùng tô đáp án với độ chính xác cao.
* **Quản lý theo ngữ cảnh:** Hỗ trợ nhập thông tin Tên Lớp, Ngày thi, Bộ đề và Mã đề.
* **Lưu trữ tập trung:** * Tự động tổng hợp kết quả vào file duy nhất `data/master.csv`.
    * Cơ chế thông minh: Tự động ghi đè (overwrite) nếu chấm lại bài cũ, đảm bảo tính nhất quán dữ liệu.
* **Chế độ Review (Review Window):** Giao diện riêng biệt để xem lại bài thi, so sánh đáp án máy chấm và thực tế để chỉnh sửa sai sót.
* **Báo cáo chi tiết:** Xuất điểm tổng, điểm thành phần (LC/RC) và chi tiết từng part.

## 3. Cấu trúc dự án
Dự án được tổ chức theo cấu trúc tiêu chuẩn, dễ dàng mở rộng và bảo trì:

```text
toeic_omr/
│
├── config/                 # Chứa file cấu hình, tách biệt code và dữ liệu
│   ├── app_config.json     # Cấu hình màu sắc, tham số thuật toán
│   ├── key.json            # Dữ liệu Đáp án
│   └── scoring_ref.json    # Bảng quy đổi điểm (Thang điểm)
│
├── logs/                   # Nơi chứa file log và ảnh kết quả từng phiên
│
├── src/                    # Source code chính
│   ├── __init__.py
│   ├── main.py             # Điểm khởi chạy chương trình
│   │
│   ├── utils/              # Các tiện ích bổ trợ (non-logic)
│   │   ├── __init__.py
│   │   ├── logger.py       # Thiết lập logging tập trung
│   │   ├── file_io.py      # Xử lý Đọc/Ghi (JSON, CSV) - Class FileHandler
│   │   └── helpers.py
│   │
│   ├── core/               # Logic chính
│   │   ├── __init__.py
│   │   ├── warp_processor.py   # Xử lý căn chỉnh, cắt ảnh
│   │   ├── omr_engine.py       # Nhận diện vùng tô đáp án
│   │   └── grade_manager.py    # Xử lý tính điểm và format kết quả
│   │
│   ├── ui/                 # Giao diện người dùng
│   │   ├── __init__.py
│   │   ├── app_window.py       # Cửa sổ chính (Main Dashboard)
│   │   ├── review_window.py    # Cửa sổ xem lại bài thi (Review Mode)
│   │   ├── components.py       # Các widget tái sử dụng
│   │   └── state_manager.py    # Quản lý trạng thái form và validate dữ liệu
│   │
│   └── workers/            
│       ├── __init__.py
│       └── scoring_worker.py   # Xử lý đa luồng (Threading) để không treo UI
│
├── tests/                  # Chứa các ảnh bài làm mẫu để kiểm thử
├── requirements.txt        # Danh sách thư viện phụ thuộc
└── README.md               # Tài liệu hướng dẫn

## 4. Yêu cầu hệ thống

* **Ngôn ngữ:** Python 3.8 trở lên.
* **Thư viện:** OpenCV, Numpy, Pandas, Pillow.

## 5. Hướng dẫn cài đặt & Chạy

**Bước 1:** Cài đặt thư viện
Tại thư mục gốc `toeic_omr`, chạy lệnh:

```bash
pip install -r requirements.txt

```

**Bước 2:** Khởi chạy phần mềm
Khởi động Terminal tại thư mục `toeic-omr` và chạy lệnh:

```bash
python src/main.py

```

## 6. Hướng dẫn sử dụng

1. **Thiết lập thông tin:**
* Chọn **Bộ đề (Set)** và **Mã đề (Test ID)**.
* Nhập **Tên Lớp (Class)** (Bắt buộc) và kiểm tra **Ngày thi**.


2. **Nhập dữ liệu ảnh:**
* Nhấn nút **Browse** để chọn file ảnh phiếu thi từ thư mục `tests/` hoặc thư mục bất kỳ.


3. **Thực hiện chấm:**
* Nhấn nút **Play (▶)** để bắt đầu quá trình xử lý.


4. **Kiểm tra & Lưu:**
* Sau khi chấm xong, click vào từng dòng trên bảng để mở **Review Window**.
* Nhấn nút **Save & Upload** để lưu kết quả tổng hợp vào `data/master.csv`.


---

*Bài tập lớn môn Lập Trình Python cho Học máy*

```

```