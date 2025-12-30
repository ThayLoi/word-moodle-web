import streamlit as st
import os
import shutil
import tempfile
import zipfile
import time
from pathlib import Path
import extra_streamlit_components as stx
import sys

# --- CẤU HÌNH ĐƯỜNG DẪN ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from appword.services.pipeline import run_pipeline
except ImportError as e:
    st.error(f"Lỗi module: {e}")
    st.stop()

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Word to Moodle",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS TỐI ƯU GIAO DIỆN (COMPACT) ---
st.markdown("""
<style>
    /* Thu gọn khoảng trắng thừa ở đầu trang */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }
    /* Chỉnh lại tiêu đề cho gọn */
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0.5rem !important;
    }
    /* Nút bấm đẹp hơn */
    div.stButton > button:first-child {
        background-color: #0068c9; color: white; border-radius: 6px; font-weight: 600;
    }
    /* Thông báo thành công gọn hơn */
    .stSuccess {
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- KHỞI TẠO COOKIE ---
cookie_manager = stx.CookieManager()

# --- AUTHENTICATION (GIỮ NGUYÊN) ---
def check_authentication():
    try:
        allowed_emails = st.secrets["general"]["allowed_emails"]
    except:
        allowed_emails = [] 

    if "user_email" in st.session_state: return True
    time.sleep(0.1) 
    saved_email = cookie_manager.get("user_email")
    if saved_email and (not allowed_emails or saved_email in allowed_emails):
        st.session_state["user_email"] = saved_email
        return True
    return False

def login_screen():
    st.title("🔐 Đăng nhập")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        email = st.text_input("Email:", placeholder="admin@school.edu.vn")
        if st.button("Truy cập", use_container_width=True):
            try:
                allowed = st.secrets["general"]["allowed_emails"]
                if email.strip() in allowed:
                    st.session_state["user_email"] = email.strip()
                    cookie_manager.set("user_email", email.strip(), key="email_ck")
                    st.rerun()
                else:
                    st.error("Không có quyền truy cập.")
            except:
                st.session_state["user_email"] = email; st.rerun()

if not check_authentication():
    login_screen()
    st.stop()

user_email = st.session_state.get("user_email", "User")

# ================= GIAO DIỆN CHÍNH =================

# --- SIDEBAR (CHỨA CẤU HÌNH & USER) ---
with st.sidebar:
    st.caption(f"👤 {user_email}")
    if st.button("Đăng xuất", key="logout_btn", use_container_width=True):
        cookie_manager.delete("user_email")
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    st.header("⚙️ Cấu hình hệ thống")
    
    # 1. API KEY
    with st.expander("🔑 ImgBB API Key", expanded=True):
        cookie_key = cookie_manager.get("my_imgbb_key")
        api_key_input = st.text_input("Nhập Key:", value=cookie_key if cookie_key else "", type="password")
        c_save, c_del = st.columns(2)
        if c_save.button("Lưu"):
            cookie_manager.set("my_imgbb_key", api_key_input, key="save_api")
            st.toast("Đã lưu API Key!")
            time.sleep(1)
        if c_del.button("Xóa"):
            cookie_manager.delete("my_imgbb_key")
            st.rerun()

    # 2. MAPPING ID
    with st.expander("📂 File ID Mapping", expanded=True):
        repo_path = os.path.join(os.getcwd(), "ID")
        defaults = [f for f in os.listdir(repo_path) if f.endswith(".xlsx")] if os.path.exists(repo_path) else []
        
        map_mode = st.radio("Nguồn:", ["Mặc định", "Upload"], horizontal=True, label_visibility="collapsed")
        
        final_mapping_source = None
        if map_mode == "Mặc định" and defaults:
            sel = st.selectbox("Chọn file:", defaults)
            if sel: final_mapping_source = os.path.join(repo_path, sel)
        else:
            up_map = st.file_uploader("File Excel:", type=['xlsx'])
            if up_map: final_mapping_source = up_map

    st.info("ℹ️ Tải file Word lên màn hình chính để xử lý.")

# --- MAIN SCREEN (TẬP TRUNG XỬ LÝ) ---
st.title("📝 Chuyển đổi Word ➡️ Moodle XML")

# Khu vực Upload File (Làm to và rõ)
upload_container = st.container()
with upload_container:
    uploaded_word_files = st.file_uploader(
        "Kéo thả hoặc chọn file đề trắc nghiệm (.docx)", 
        type=['docx'], 
        accept_multiple_files=True
    )

# Khu vực Action & Result
if uploaded_word_files:
    # Hiển thị số lượng file đã chọn
    st.write(f"📁 **Đã nhận {len(uploaded_word_files)} file.** Nhấn nút bên dưới để bắt đầu.")
    
    # Nút bấm to, rõ ràng
    if st.button("🚀 BẮT ĐẦU XỬ LÝ NGAY", type="primary", use_container_width=True):
        
        # --- LOGIC XỬ LÝ (GIỮ NGUYÊN) ---
        run_api_key = api_key_input
        if not run_api_key:
            try: run_api_key = st.secrets["general"]["default_imgbb_key"]
            except: pass
        
        if not final_mapping_source:
            st.warning("⚠️ Chưa chọn file ID Mapping (trong Sidebar).")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            in_d, out_d, map_d = base/"input", base/"output", base/"mapping"
            for d in [in_d, out_d, map_d]: d.mkdir()

            # Status log gọn gàng
            status_box = st.status("Dang xử lý...", expanded=True)
            
            # 1. Setup Mapping
            real_map_arg = None
            if final_mapping_source:
                if isinstance(final_mapping_source, str):
                    shutil.copy(final_mapping_source, map_d / os.path.basename(final_mapping_source))
                else:
                    with open(map_d / final_mapping_source.name, "wb") as f: f.write(final_mapping_source.getbuffer())
                real_map_arg = str(map_d)

            # 2. Save Docs
            for uf in uploaded_word_files:
                with open(in_d / uf.name, "wb") as f: f.write(uf.getbuffer())
            
            # 3. Run Pipeline
            prog = status_box.progress(0)
            def on_prog(c, t, m): prog.progress(min(int((c/t)*100), 100)); status_box.write(f"⚙️ {m}")

            try:
                run_pipeline(str(in_d), str(out_d), run_api_key, on_prog, real_map_arg)
                status_box.update(label="✅ Thành công!", state="complete", expanded=False)
                
                # 4. Zip & Download
                zip_name = "ket_qua_moodle.zip"
                zip_f = base / zip_name
                with zipfile.ZipFile(zip_f, 'w', zipfile.ZIP_DEFLATED) as z:
                    for r, _, fs in os.walk(out_d):
                        for file in fs: z.write(os.path.join(r, file), os.path.relpath(os.path.join(r, file), out_d))
                
                with open(zip_f, "rb") as f:
                    st.download_button(
                        label="📥 TẢI KẾT QUẢ VỀ MÁY",
                        data=f,
                        file_name=zip_name,
                        mime="application/zip",
                        type="primary",
                        use_container_width=True
                    )
                
                # Show list file
                with st.expander("Xem danh sách file chi tiết"):
                    st.json(os.listdir(out_d))

            except Exception as e:
                status_box.update(label="❌ Thất bại", state="error")
                st.error(f"Lỗi: {str(e)}")

else:
    # Khi chưa upload file thì hiện hướng dẫn ngắn
    st.info("👈 Vui lòng kiểm tra cấu hình bên thanh trái, sau đó upload file để bắt đầu.")
