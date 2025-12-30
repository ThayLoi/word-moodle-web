import hashlib
import hmac
import datetime
import subprocess
import os
import sys

# --- CẤU HÌNH BÍ MẬT (CHỈ MÌNH BẠN BIẾT) ---
# Hãy đổi chuỗi này thành cái gì đó thật dài và ngẫu nhiên
SECRET_KEY = b"WordMoodle_Secret_Key_2025_@#$!_ChangeMe"

def get_machine_code():
    """Lấy mã máy dựa trên UUID của ổ cứng (Windows)"""
    try:
        # Lấy serial ổ đĩa C
        cmd = 'wmic csproduct get uuid'
        uuid = subprocess.check_output(cmd).decode().split('\n')[1].strip()
        # Hash lại cho ngắn gọn và đẹp
        return hashlib.md5(uuid.encode()).hexdigest().upper()
    except Exception:
        return "UNKNOWN-MACHINE-ID"

def generate_license_key(machine_code, expiry_date_str):
    """
    Tạo License Key (Dành cho Admin Tool).
    Format Key: EXPIRYDATE-SIGNATURE
    Ví dụ: 20251231-A1B2C3D4...
    """
    # Dữ liệu cần ký: Mã máy + Ngày hết hạn
    data = f"{machine_code}|{expiry_date_str}".encode()
    
    # Tạo chữ ký HMAC (An toàn hơn hash thường)
    signature = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()[:16].upper()
    
    # Key cuối cùng = Ngày hết hạn + Chữ ký
    final_key = f"{expiry_date_str}-{signature}"
    return final_key

def verify_license(machine_code, input_key):
    """
    Kiểm tra Key có hợp lệ không.
    Trả về: (Trạng thái True/False, Thông báo)
    """
    try:
        if "-" not in input_key:
            return False, "Key sai định dạng."

        # Tách ngày hết hạn và chữ ký từ Key người dùng nhập
        expiry_date_str, input_signature = input_key.split("-")
        
        # 1. Tự tính toán lại chữ ký xem có khớp không
        data = f"{machine_code}|{expiry_date_str}".encode()
        expected_signature = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()[:16].upper()
        
        if input_signature != expected_signature:
            return False, "Key không hợp lệ cho máy này."
            
        # 2. Kiểm tra hạn sử dụng
        expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y%m%d")
        if datetime.datetime.now() > expiry_date:
            return False, f"Key đã hết hạn vào ngày {expiry_date.strftime('%d/%m/%Y')}."

        return True, f"Bản quyền hợp lệ đến: {expiry_date.strftime('%d/%m/%Y')}"

    except Exception as e:
        return False, "Lỗi kiểm tra bản quyền."