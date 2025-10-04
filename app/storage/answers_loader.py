import os
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "../../data/answers")

def list_sets(overview_file=os.path.join(BASE_DIR, "../../data/sets_overview.csv")):
    """Đọc sets_overview.csv → trả về danh sách (set_name, num_codes)."""
    sets = []
    with open(overview_file, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sets.append((row["set_name"], int(row["num_codes"])))
    return sets

def list_codes(set_name):
    """Trả về list mã đề của 1 bộ đề (dựa trên file CSV)."""
    filepath = os.path.join(DATA_DIR, f"{set_name}.csv")
    codes = []
    with open(filepath, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            codes.append(int(row["code"]))
    return codes

def get_answers(set_name, code):
    """Trả về chuỗi đáp án (200 ký tự) của 1 bộ đề + mã đề."""
    filepath = os.path.join(DATA_DIR, f"{set_name}.csv")
    with open(filepath, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["code"]) == int(code):
                return row["answers"].strip()
    raise ValueError(f"Không tìm thấy mã đề {code} trong {set_name}")
