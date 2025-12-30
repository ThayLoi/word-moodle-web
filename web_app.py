import streamlit as st
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

# Import logic cũ của bạn
# (Đảm bảo Python tìm thấy thư mục appword)
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from appword.services.pipeline import run_pipeline

# --- CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Word to Moodle XML", page_icon="📝", layout="wide")

# --- CSS TÙY CHỈNH CHO ĐẸP ---
st.markdown("""
<style>
    .main {background-color: #f5f5f5;}
    div.stButton > button:first-child {
        background-color: #0068c9; color: white; width: 100%; height: 3em;
    }
</style>
""", unsafe_allow_html=True)

# --- PHẦN ĐĂNG NHẬP ĐƠN GIẢN (THAY CHO LICENSE KEY) ---
def check_password():
    """Returns `True` if the user had a correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] in ["admin123", "vipuser2025"]: # <--- DANH SÁCH MẬT KHẨU/KEY
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Nhập Mã truy cập (License Key):", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Nhập Mã truy cập (License Key):", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Sai mã rồi, vui lòng liên hệ Admin.")
        return False
    else:
        # Password correct.
        return True

if not check_password():
    st.stop()  # Dừng app nếu chưa đăng nhập

# --- GIAO DIỆN CHÍNH ---
st.title("📝 Chuyển đổi Word sang Moodle XML")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Cấu hình")
    api_key = st.text_input("ImgBB API Key (Tùy chọn)", type="password", help="Để trống sẽ dùng key mặc định của hệ thống")
    
    # Nơi upload file Excel ID (Mapping)
    uploaded_mapping = st.file_uploader("File ID Mapping (.xlsx)", type=['xlsx'], accept_multiple_files=False)
    
    st.info("💡 Hướng dẫn: Upload file Word chứa câu hỏi trắc nghiệm, hệ thống sẽ tách ảnh, upload lên web và tạo file XML.")

with col2:
    st.header("2. Upload & Xử lý")
    uploaded_files = st.file_uploader("Chọn file Word (.docx)", type=['docx'], accept_multiple_files=True)

    if uploaded_files:
        if st.button(f"🚀 BẮT ĐẦU XỬ LÝ ({len(uploaded_files)} file)"):
            
            # --- TẠO MÔI TRƯỜNG TẠM ---
            # Web server cần chỗ để lưu file tạm thời
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                input_dir = temp_path / "input"
                output_dir = temp_path / "output"
                mapping_dir = temp_path / "mapping"
                
                input_dir.mkdir()
                output_dir.mkdir()
                mapping_dir.mkdir()

                # 1. Lưu file mapping (nếu có)
                if uploaded_mapping:
                    with open(mapping_dir / uploaded_mapping.name, "wb") as f:
                        f.write(uploaded_mapping.getbuffer())

                # 2. Lưu các file Word tải lên vào thư mục input
                st.write("Đang lưu file...")
                for uploaded_file in uploaded_files:
                    with open(input_dir / uploaded_file.name, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                # 3. CHẠY PIPELINE (Gọi code cũ của bạn)
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current, total, msg):
                    percent = int((current / total) * 100)
                    progress_bar.progress(min(percent, 100))
                    status_text.text(f"Đang xử lý: {msg}")

                try:
                    # Gọi hàm xử lý chính
                    run_pipeline(
                        input_folder=str(input_dir),
                        output_folder=str(output_dir),
                        api_key=api_key if api_key else None, # Nếu user không nhập thì để None (code cũ tự lo)
                        progress_cb=update_progress,
                        mapping_dir=str(mapping_dir) if uploaded_mapping else None
                    )

                    st.success("✅ Xử lý hoàn tất!")

                    # 4. Nén kết quả thành ZIP để tải về
                    zip_path = temp_path / "ket_qua_moodle.zip"
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(output_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, output_dir)
                                zipf.write(file_path, arcname)

                    # 5. Tạo nút Download
                    with open(zip_path, "rb") as f:
                        st.download_button(
                            label="📥 Tải xuống kết quả (.zip)",
                            data=f,
                            file_name="ket_qua_moodle.zip",
                            mime="application/zip"
                        )
                    
                    # Hiển thị thống kê nhanh
                    st.subheader("Kết quả chi tiết:")
                    for file in os.listdir(output_dir):
                        if file.endswith(".json"):
                            st.text(f"- {file}")

                except Exception as e:
                    st.error(f"Có lỗi xảy ra: {str(e)}")
                    # Hiện chi tiết lỗi cho dev xem
                    # st.exception(e)