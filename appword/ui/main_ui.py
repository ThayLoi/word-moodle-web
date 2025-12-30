# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import uuid
import hashlib
import platform
import traceback
from functools import partial
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PyQt5 import QtWidgets, QtCore, QtGui
import xml.etree.ElementTree as ET

# --- Import pipeline ---
try:
    from appword.services.pipeline import run_pipeline
except ModuleNotFoundError:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from appword.services.pipeline import run_pipeline

APP_NAME = "Moodle Questions"
APP_VERSION = "1.2.0"

# ================= PATH HELPERS (QUAN TRỌNG) =================
def get_app_path():
    """ Lấy đường dẫn nơi chứa file .exe (hoặc file script) """
    if getattr(sys, 'frozen', False):
        # Nếu đang chạy file .exe
        return os.path.dirname(sys.executable)
    else:
        # Nếu đang chạy code python thường
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """ Lấy đường dẫn tài nguyên (bên trong file đóng gói) """
    try:
        # PyInstaller tạo ra folder tạm này
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================= CONFIG LOCATION =================
# Thiết lập file cấu hình nằm trong thư mục 'configs' cạnh file .exe
APP_DIR = Path(get_app_path())
CONFIG_DIR = APP_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "settings.json"

# ================= Config helpers =================
def load_user_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_user_config(cfg: dict) -> None:
    try:
        # Tạo thư mục configs nếu chưa có
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Ghi file
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Không thể lưu cấu hình: {e}")

# ================= License helpers (fallback offline) =================
def get_machine_code() -> str:
    raw = f"{uuid.getnode():012x}|{platform.system()}|{platform.release()}|{platform.node()}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    core = h[:20]
    return "-".join(core[i:i + 5] for i in range(0, 20, 5))

def normalize_key(s: str) -> str:
    s = "".join(c for c in s.upper() if c.isalnum())
    chunks = [s[i:i + 5] for i in range(0, len(s), 5)]
    return "-".join(chunks)

def generate_expected_key(machine_code: str) -> str:
    base = ("APPWORD-" + machine_code).encode("utf-8")
    h = hashlib.sha256(base).hexdigest().upper()[:20]
    return "-".join(h[i:i + 5] for i in range(0, 20, 5))

def validate_license(machine_code: str, license_key: str) -> bool:
    return normalize_key(license_key) == generate_expected_key(machine_code)

def _b64url_pad(s: str) -> str:
    t = (s or "").strip().replace(" ", "")
    t = t.replace("-", "+").replace("_", "/")
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return t

def _normalize_signed_token(token: str) -> str:
    tok = (token or "").strip()
    if "." in tok:
        parts = tok.split(".")
        parts = [_b64url_pad(p) for p in parts]
        return ".".join(parts)
    return _b64url_pad(tok)

# ================= JSON stats helpers =================
def _iter_questions(data) -> List[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict) and x.get("question_type")]
    elif isinstance(data, dict):
        items = data.get("questions") or data.get("items") or []
        return [x for x in items if isinstance(x, dict) and x.get("question_type")]
    return []

def _count_images_in_question(q: dict) -> Tuple[int, int]:
    total = 0
    online = 0
    if q.get("question_image") or q.get("question_image_url"):
        total += 1
        if q.get("question_image_url"):
            online += 1
    for opt in q.get("options") or []:
        if not isinstance(opt, dict):
            continue
        if opt.get("option_image") or opt.get("option_image_url"):
            total += 1
            if opt.get("option_image_url"):
                online += 1
    expl = q.get("explanation") or {}
    if isinstance(expl, dict) and (expl.get("image") or expl.get("image_url")):
        total += 1
        if expl.get("image_url"):
            online += 1
    return online, total

def _stats_from_uploaded_json(json_path: Path) -> Dict[str, int]:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return dict(questions=0, multichoice=0, kprime=0, shortanswer=0,
                    images_online=0, images_total=0)
    qs = _iter_questions(data)
    mc = sum(1 for q in qs if q.get("question_type") == "multichoice")
    kp = sum(1 for q in qs if q.get("question_type") in ("kprime", "truefalse", "tf", "true_false"))
    sa = sum(1 for q in qs if q.get("question_type") == "shortanswer")

    img_online = 0
    img_total = 0
    for q in qs:
        o, t = _count_images_in_question(q)
        img_online += o
        img_total += t

    return dict(
        questions=len(qs),
        multichoice=mc,
        kprime=kp,
        shortanswer=sa,
        images_online=img_online,
        images_total=img_total,
    )

def _merge_stats(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    keys = ("questions", "multichoice", "kprime", "shortanswer", "images_online", "images_total")
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in keys}

# ================= Worker thread =================
class PipelineThread(QtCore.QThread):
    progress_changed = QtCore.pyqtSignal(int, int, str)
    finished_with_result = QtCore.pyqtSignal(dict)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, input_dir: str, output_dir: str, mapping_dir: str = "", api_key: str = "", parent=None):
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.mapping_dir = mapping_dir
        self.api_key = api_key
        self._planned_inputs: List[Path] = self._plan_inputs()

    def _plan_inputs(self) -> List[Path]:
        if not self.input_dir.exists():
            return []
        docxs = sorted(p for p in self.input_dir.rglob("*.docx") if not p.name.startswith("~$"))
        if docxs:
            return docxs
        jsons = [
            p for p in self.input_dir.rglob("*.json")
            if p.name.endswith("questionsTF.json")
            and not p.name.endswith(".uploaded.json")
            and not p.name.startswith("~$")
        ]
        return sorted(jsons)

    def _map_outputs_for_input(self, inp: Path) -> Tuple[Optional[Path], Optional[Path]]:
        if inp.suffix.lower() == ".docx":
            per = self.output_dir / inp.stem
            candidates = [per / "questionsTF.uploaded.json", per / f"{inp.stem}.uploaded.json"]
            uploaded_json = next((p for p in candidates if p.exists()), candidates[0])
            xml_out = per / "moodle.xml"
            return uploaded_json, xml_out
        else:
            try:
                rel = inp.relative_to(self.input_dir)
            except Exception:
                rel = Path(inp.name)
            out_json = (self.output_dir / rel).with_suffix(".uploaded.json")
            out_xml = (self.output_dir / rel).with_suffix(".xml")
            return out_json, out_xml

    @staticmethod
    def _count_suspect_names(xml_path: Path) -> int:
        try:
            if not xml_path or not xml_path.exists():
                return 0
            pat = re.compile(r"^\s*Q\d+\s*(\|\s*Mã đề:\s*.+)?$", re.IGNORECASE)
            tree = ET.parse(str(xml_path))
            root = tree.getroot()
            bad = 0
            for q in root.findall(".//question"):
                name_el = q.find("./name")
                if name_el is None:
                    continue
                text_el = name_el.find("./text")
                if text_el is None:
                    continue
                cur = (text_el.text or "").strip()
                if pat.fullmatch(cur):
                    bad += 1
            return bad
        except Exception:
            return 0

    def run(self):
        try:
            def cb(i, total, msg):
                self.progress_changed.emit(i, total, str(msg or ""))

            # Ưu tiên lấy API key từ tham số truyền vào (đã load từ config)
            api = self.api_key.strip() or os.getenv("IMGBB_API_KEY") or ""

            run_pipeline(
                str(self.input_dir),
                str(self.output_dir),
                api_key=api,
                progress_cb=cb,
                mapping_dir=(self.mapping_dir or None),
            )

            files_result: List[dict] = []
            totals = dict(questions=0, multichoice=0, kprime=0, shortanswer=0,
                          images_online=0, images_total=0, suspect_names=0)

            for inp in self._planned_inputs:
                out_json, out_xml = self._map_outputs_for_input(inp)
                stats = dict(questions=0, multichoice=0, kprime=0, shortanswer=0,
                             images_online=0, images_total=0)
                flags = dict(suspect_names=0)
                ok = False
                err = ""
                try:
                    if out_json and not out_json.exists() and inp.suffix.lower() == ".docx":
                        per = self.output_dir / inp.stem
                        found = sorted(per.glob("*.uploaded.json"))
                        if found:
                            out_json = found[0]

                    if out_json and out_json.exists():
                        stats = _stats_from_uploaded_json(out_json)
                        ok = True
                    else:
                        err = "Không tìm thấy file *.uploaded.json sau khi xử lý."

                    if out_xml and Path(out_xml).exists():
                        flags["suspect_names"] = self._count_suspect_names(Path(out_xml))
                except Exception as e:
                    err = str(e)

                totals = _merge_stats(totals, stats)
                totals["suspect_names"] = totals.get("suspect_names", 0) + int(flags["suspect_names"])

                files_result.append({
                    "input": str(inp),
                    "output_json": str(out_json) if out_json else "",
                    "output_xml": str(out_xml) if out_xml else "",
                    "ok": ok,
                    "stats": stats,
                    "flags": flags,
                    "error": err
                })

            self.finished_with_result.emit({"files": files_result, "totals": totals})
        except Exception:
            self.failed.emit(traceback.format_exc())

# ================= Main UI =================
class MainUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Chuyển file Word.docx -> Chuẩn Moodle")
        self.resize(1080, 720)
        
        # Load icon từ resource path nếu có
        try:
            icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
            if os.path.exists(icon_path):
                self.setWindowIcon(QtGui.QIcon(icon_path))
        except: pass

        # Tabs
        self.tabs = QtWidgets.QTabWidget(self)
        main_tab = QtWidgets.QWidget(self)
        exam_tab = QtWidgets.QWidget(self)      # Thao tác XML
        help_tab = QtWidgets.QWidget(self)
        settings_tab = QtWidgets.QWidget(self)  # Cấu hình (API key)
        license_tab = QtWidgets.QWidget(self)

        # ---------- Tab 1: Xử lý ----------
        self.input_edit = QtWidgets.QLineEdit()
        self.output_edit = QtWidgets.QLineEdit()
        self.map_edit = QtWidgets.QLineEdit()

        self.btn_browse_input = QtWidgets.QPushButton("Chọn Input")
        self.btn_open_input = QtWidgets.QPushButton("Mở Input")
        self.btn_browse_output = QtWidgets.QPushButton("Chọn Output")
        self.btn_open_output = QtWidgets.QPushButton("Mở Output")
        self.btn_browse_map = QtWidgets.QPushButton("Chọn ID")
        self.btn_open_map = QtWidgets.QPushButton("Mở ID")
        self.btn_run = QtWidgets.QPushButton("Chạy xử lý")

        self.progress = QtWidgets.QProgressBar()
        self.progress.setFormat("%p%")
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#333;")
        self.warn_label = QtWidgets.QLabel("")
        self.warn_label.setStyleSheet("color:#b00020;")
        self.warn_label.setWordWrap(True)

        self.result_table = QtWidgets.QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(["File", "Câu hỏi", "Loại", "Ảnh online", "Mở chứa XML"])
        header = self.result_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.result_table.setWordWrap(True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.result_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.result_table.setMinimumHeight(300)

        main_layout = QtWidgets.QVBoxLayout(main_tab)
        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(QtWidgets.QLabel("Folder Input:"))
        h1.addWidget(self.input_edit); h1.addWidget(self.btn_browse_input); h1.addWidget(self.btn_open_input)
        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(QtWidgets.QLabel("Folder Output:"))
        h2.addWidget(self.output_edit); h2.addWidget(self.btn_browse_output); h2.addWidget(self.btn_open_output)
        h3 = QtWidgets.QHBoxLayout()
        h3.addWidget(QtWidgets.QLabel("Thư mục ID (Excel):"))
        h3.addWidget(self.map_edit); h3.addWidget(self.btn_browse_map); h3.addWidget(self.btn_open_map)

        main_layout.addLayout(h1); main_layout.addLayout(h2); main_layout.addLayout(h3)
        main_layout.addWidget(self.btn_run); main_layout.addWidget(self.progress)
        main_layout.addWidget(self.status_label); main_layout.addWidget(self.warn_label)
        main_layout.addWidget(self.result_table)

        # ---------- Tab 2: Thao tác XML ----------
        exam_layout = QtWidgets.QVBoxLayout(exam_tab)
        form = QtWidgets.QFormLayout()

        # Chọn nguồn XML
        self.btn_pick_xml = QtWidgets.QPushButton("Chọn nguồn XML")
        menu = QtWidgets.QMenu(self.btn_pick_xml)
        act_files = menu.addAction("Chọn file XML...")
        act_dir = menu.addAction("Chọn thư mục chứa XML...")
        self.btn_pick_xml.setMenu(menu)
        self.exam_xml_edit = QtWidgets.QLineEdit(); self.exam_xml_edit.setReadOnly(True)
        row_src = QtWidgets.QHBoxLayout(); row_src.addWidget(self.btn_pick_xml); row_src.addWidget(self.exam_xml_edit, 1)
        src_wrap = QtWidgets.QWidget(); src_wrap.setLayout(row_src)
        form.addRow("Nguồn XML:", src_wrap)

        self.lbl_xml_hint = QtWidgets.QLabel(""); self.lbl_xml_hint.setWordWrap(True)
        self.lbl_xml_hint.setStyleSheet("color:#b00020;")
        form.addRow("", self.lbl_xml_hint)

        # A) Cập nhật Category (độc lập) – đồng thời chuẩn hoá <name> = leaf-category
        self.category_edit = QtWidgets.QLineEdit()
        self.category_edit.setPlaceholderText("$course$/top/Toán 10/Chương 1/TO12.04.1.F02.a Ứng dụng nguyên hàm")
        self.btn_open_id_src = QtWidgets.QToolButton(); self.btn_open_id_src.setText("📁")
        self.btn_open_id_src.setToolTip("Mở thư mục ID (Excel)")
        cat_row = QtWidgets.QHBoxLayout(); cat_row.addWidget(self.btn_open_id_src); cat_row.addWidget(self.category_edit)
        cat_wrap = QtWidgets.QWidget(); cat_wrap.setLayout(cat_row)
        form.addRow("Category:", cat_wrap)
        self.btn_update_category = QtWidgets.QPushButton("Cập nhật Category vào XML (và chuẩn hoá <name> = leaf-category)")
        form.addRow("", self.btn_update_category)

        # B) Thêm mã đề (độc lập) – chỉ thêm/ghi đè tail “| Mã đề: …”
        self.exam_code_edit = QtWidgets.QLineEdit()
        self.exam_code_edit.setPlaceholderText("Nhập mã đề (ví dụ: A, B hoặc 12345)")
        form.addRow("Mã đề:", self.exam_code_edit)
        self.btn_assign_examcode = QtWidgets.QPushButton("Thêm/ghi đè mã đề cho TẤT CẢ câu hỏi (không đổi phần tên)")
        form.addRow("", self.btn_assign_examcode)

        exam_layout.addLayout(form); exam_layout.addStretch(1)

        # ---------- Tab 3: Hướng dẫn ----------
        help_layout = QtWidgets.QVBoxLayout(help_tab)
        self.help_view = QtWidgets.QTextBrowser(); self.help_view.setOpenExternalLinks(True)
        self.help_view.setHtml("""
            <h3>Quy trình khuyến nghị</h3>
            <ol>
              <li>Nếu XML <b>chưa có/đổi Category</b>: nhập Category và bấm <b>Cập nhật Category</b>.<br>
                  Hệ thống sẽ <u>đồng thời chuẩn hoá</u> mọi &lt;name&gt; = leaf-category.</li>
              <li>Sau đó, để thêm mã đề: nhập mã và bấm <b>Thêm/ghi đè mã đề</b> (chỉ ghi phần “| Mã đề: …”).</li>
            </ol>
        """)
        help_layout.addWidget(self.help_view)

        # ---------- Tab 4: Cấu hình ----------
        settings_layout = QtWidgets.QFormLayout(settings_tab)
        self.api_edit = QtWidgets.QLineEdit()
        self.api_edit.setPlaceholderText("IMGBB API key (để trống: dùng IMGBB_API_KEY trong ENV)")
        self.btn_save_settings = QtWidgets.QPushButton("Lưu cấu hình")
        row_save = QtWidgets.QHBoxLayout(); row_save.addWidget(self.btn_save_settings); row_save.addStretch(1)
        wrap_save = QtWidgets.QWidget(); wrap_save.setLayout(row_save)
        settings_layout.addRow("API key:", self.api_edit); settings_layout.addRow("", wrap_save)

        # ---------- Tab 5: Kích hoạt ----------
        lic_layout = QtWidgets.QFormLayout(license_tab)
        self.lbl_app = QtWidgets.QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.lbl_machine = QtWidgets.QLineEdit(); self.lbl_machine.setReadOnly(True)
        self.btn_copy_machine = QtWidgets.QPushButton("Sao chép mã máy")
        row_machine = QtWidgets.QHBoxLayout(); row_machine.addWidget(self.lbl_machine); row_machine.addWidget(self.btn_copy_machine)
        wrap_machine = QtWidgets.QWidget(); wrap_machine.setLayout(row_machine)
        self.license_edit = QtWidgets.QLineEdit(); self.license_edit.setPlaceholderText("Nhập License Key")
        self.lbl_status = QtWidgets.QLabel("Chưa kích hoạt")
        self.btn_activate = QtWidgets.QPushButton("Kích hoạt")
        self.btn_deactivate = QtWidgets.QPushButton("Xóa kích hoạt")
        row_act = QtWidgets.QHBoxLayout(); row_act.addWidget(self.btn_activate); row_act.addWidget(self.btn_deactivate)
        wrap_act = QtWidgets.QWidget(); wrap_act.setLayout(row_act)
        lic_layout.addRow("Ứng dụng:", self.lbl_app)
        lic_layout.addRow("Mã máy:", wrap_machine)
        lic_layout.addRow("License Key:", self.license_edit)
        lic_layout.addRow("Trạng thái:", self.lbl_status)
        lic_layout.addRow("", wrap_act)

        # Tabs
        self.tabs.addTab(main_tab, "Xử lý")
        self.tabs.addTab(exam_tab, "Thao tác XML")
        self.tabs.addTab(help_tab, "Hướng dẫn")
        self.tabs.addTab(settings_tab, "Cấu hình")
        self.tabs.addTab(license_tab, "Kích hoạt")

        root = QtWidgets.QVBoxLayout(self); root.addWidget(self.tabs)

        # Signals
        self.btn_browse_input.clicked.connect(self.select_input_folder)
        self.btn_open_input.clicked.connect(self.open_input_folder)
        self.btn_browse_output.clicked.connect(self.select_output_folder)
        self.btn_open_output.clicked.connect(self.open_output_folder)
        self.btn_browse_map.clicked.connect(self.select_map_folder)
        self.btn_open_map.clicked.connect(self.open_map_folder)
        self.btn_run.clicked.connect(self.run_process)

        self.btn_copy_machine.clicked.connect(self.copy_machine_code)
        self.btn_activate.clicked.connect(self.activate_license)
        self.btn_deactivate.clicked.connect(self.deactivate_license)

        act_files.triggered.connect(self._pick_xml_files)
        act_dir.triggered.connect(self._pick_xml_dir)
        self.btn_open_id_src.clicked.connect(self.open_id_source)

        self.btn_update_category.clicked.connect(self._apply_update_category)
        self.btn_assign_examcode.clicked.connect(self._apply_assign_examcode)

        self.btn_save_settings.clicked.connect(self._save_config_from_ui)

        self.worker: Optional[PipelineThread] = None
        self._load_config_to_ui()

        self._enable_drag_drop(self.input_edit)
        self._enable_drag_drop(self.output_edit)
        self._enable_drag_drop(self.map_edit)

        self.refresh_license_ui()

    # ---------- Drag & drop ----------
    def _enable_drag_drop(self, lineedit: QtWidgets.QLineEdit):
        lineedit.setAcceptDrops(True)
        def dragEnterEvent(e): e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()
        def dropEvent(e):
            for url in e.mimeData().urls():
                p = url.toLocalFile()
                if p: lineedit.setText(p); break
        lineedit.dragEnterEvent = dragEnterEvent
        lineedit.dropEvent = dropEvent

    # ---------- Config ----------
    def _load_config_to_ui(self):
        cfg = load_user_config()
        self.input_edit.setText(cfg.get("last_input_dir", ""))
        self.output_edit.setText(cfg.get("last_output_dir", ""))
        self.map_edit.setText(cfg.get("mapping_dir", ""))
        self.api_edit.setText(cfg.get("last_api_key", ""))
        self.license_edit.setText(cfg.get("license_key", ""))

    def _save_config_from_ui(self):
        cfg = load_user_config()
        cfg["last_input_dir"] = self.input_edit.text().strip()
        cfg["last_output_dir"] = self.output_edit.text().strip()
        cfg["mapping_dir"] = self.map_edit.text().strip()
        cfg["last_api_key"] = self.api_edit.text().strip()
        cfg["license_key"] = self.license_edit.text().strip()
        save_user_config(cfg)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Đã lưu cấu hình")

    # ---------- Browse helpers ----------
    def select_input_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục Input")
        if folder: self.input_edit.setText(folder)

    def select_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục Output")
        if folder: self.output_edit.setText(folder)

    def select_map_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục ID (chứa .xlsx)")
        if folder:
            self.map_edit.setText(folder); self._save_config_from_ui()

    # ---------- Open folders ----------
    def _ensure_and_open_dir(self, path_text: str, title_missing: str):
        if not path_text:
            QtWidgets.QMessageBox.warning(self, "Thiếu đường dẫn", title_missing); return
        p = Path(path_text)
        if not p.exists():
            ans = QtWidgets.QMessageBox.question(self, "Thư mục không tồn tại",
                    f"Không tìm thấy: {p}\nBạn có muốn tạo thư mục này không?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ans == QtWidgets.QMessageBox.Yes:
                try: p.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không tạo được thư mục:\n{e}"); return
            else: return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(p)))

    def open_input_folder(self):
        path = self.input_edit.text().strip() or load_user_config().get("last_input_dir", "")
        self._ensure_and_open_dir(path, "Chưa chọn thư mục Input.")

    def open_output_folder(self):
        path = self.output_edit.text().strip() or load_user_config().get("last_output_dir", "")
        self._ensure_and_open_dir(path, "Chưa chọn thư mục Output.")

    def open_map_folder(self):
        path = self.map_edit.text().strip() or load_user_config().get("mapping_dir", "")
        self._ensure_and_open_dir(path, "Chưa chọn thư mục ID (Excel).")

    def open_id_source(self):
        path = self.map_edit.text().strip() or load_user_config().get("mapping_dir", "")
        self._ensure_and_open_dir(path, "Chưa chọn thư mục ID (Excel).")

    # ---------- Open XML container ----------
    def open_xml_container(self, xml_path: str):
        if not xml_path:
            QtWidgets.QMessageBox.warning(self, "Thiếu đường dẫn", "Chưa có đường dẫn moodle.xml cho bản ghi này."); return
        p = Path(xml_path)
        folder = p.parent if p.suffix.lower() == ".xml" else p
        if not folder.exists():
            QtWidgets.QMessageBox.warning(self, "Không tìm thấy", f"Thư mục không tồn tại:\n{folder}"); return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    # ---------- License (dual-mode: signed or offline) ----------
    def _try_signed_verify(self, key: str):
        """Trả về (ok, message). Nếu module không có, trả (None, '')."""
        try:
            from appword.licensing.machine_id import get_machine_id  # type: ignore
            from appword.licensing.verify import verify_license_string  # type: ignore
        except Exception:
            return None, ""

        mc = get_machine_id()
        # Thử nguyên bản
        try:
            payload = verify_license_string(key.strip(), mc)
            exp = payload.get("valid_to", "")
            return True, f"ĐÃ KÍCH HOẠT (hết hạn: {exp})"
        except Exception as e1:
            err = str(e1).lower()
            # Nếu lỗi base64/padding -> chuẩn hoá rồi thử lại
            if "incorrect padding" in err or "invalid base64" in err or "non-base64" in err:
                try:
                    norm_key = _normalize_signed_token(key)
                    payload = verify_license_string(norm_key, mc)
                    exp = payload.get("valid_to", "")
                    # Báo về kèm key đã chuẩn hoá để caller lưu
                    return True, f"__SAVE_NORM__{norm_key}__; ĐÃ KÍCH HOẠT (hết hạn: {exp})"
                except Exception as e2:
                    return False, f"Key không hợp lệ: {e2}"
            return False, f"Key không hợp lệ: {e1}"

    def refresh_license_ui(self):
        # Hiển thị mã máy (ưu tiên mã máy chuẩn nếu module có)
        try:
            from appword.licensing.machine_id import get_machine_id  # type: ignore
            self.lbl_machine.setText(get_machine_id())
        except Exception:
            self.lbl_machine.setText(get_machine_code())

        cfg = load_user_config()
        key = (cfg.get("license_key") or "").strip()
        if not key:
            self.lbl_status.setText("Chưa kích hoạt")
            self.lbl_status.setStyleSheet("color: #c00000;")
            return

        ok_signed, msg = self._try_signed_verify(key)
        if ok_signed is None:
            # Fallback offline
            mc = self.lbl_machine.text().strip() or get_machine_code()
            ok = validate_license(mc, key)
            self.lbl_status.setText("ĐÃ KÍCH HOẠT (offline)" if ok else "Chưa kích hoạt")
            self.lbl_status.setStyleSheet("color: #0a7c00;" if ok else "color: #c00000;")
        else:
            self.lbl_status.setText(msg if ok_signed else "Chưa kích hoạt")
            self.lbl_status.setStyleSheet("color: #0a7c00;" if ok_signed else "color: #c00000;")

    def copy_machine_code(self):
        mc = self.lbl_machine.text().strip() or get_machine_code()
        QtWidgets.QApplication.clipboard().setText(mc)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Đã sao chép mã máy")

    def activate_license(self):
        key = self.license_edit.text().strip()
        if not key:
            QtWidgets.QMessageBox.warning(self, "Thiếu key", "Nhập License Key trước khi kích hoạt."); return

        ok_signed, msg = self._try_signed_verify(key)
        if ok_signed is None:
            # Fallback offline
            mc = self.lbl_machine.text().strip() or get_machine_code()
            if validate_license(mc, key):
                cfg = load_user_config(); cfg["license_key"] = normalize_key(key); save_user_config(cfg)
                self.refresh_license_ui(); QtWidgets.QMessageBox.information(self, "Thành công", "Đã kích hoạt bản quyền (offline).")
            else:
                QtWidgets.QMessageBox.critical(self, "Key không hợp lệ",
                                            "License Key không đúng cho mã máy này.\nVui lòng kiểm tra lại.")
            return

        if ok_signed:
            norm_key = None
            if msg.startswith("__SAVE_NORM__"):
                try:
                    norm_key = msg.split("__SAVE_NORM__", 1)[1].split("__;", 1)[0]
                    msg = msg.split("__;", 1)[1]
                except Exception:
                    norm_key = None
            cfg = load_user_config(); cfg["license_key"] = norm_key or key; save_user_config(cfg)
            self.refresh_license_ui(); QtWidgets.QMessageBox.information(self, "Thành công", msg)
        else:
            QtWidgets.QMessageBox.critical(self, "Key không hợp lệ", msg)

    def deactivate_license(self):
        cfg = load_user_config()
        if "license_key" in cfg:
            cfg["license_key"] = ""
            save_user_config(cfg)
        self.refresh_license_ui()
        QtWidgets.QMessageBox.information(self, "Đã xoá", "Đã xoá thông tin kích hoạt.")

    # ---------- Run ----------
    def set_ui_enabled(self, enabled: bool):
        for w in [self.btn_browse_input, self.btn_open_input,
                  self.btn_browse_output, self.btn_open_output,
                  self.btn_browse_map, self.btn_open_map, self.btn_run,
                  self.input_edit, self.output_edit, self.map_edit,
                  self.result_table]:
            w.setEnabled(enabled)

    def run_process(self):
        input_dir = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        mapping_dir = self.map_edit.text().strip()
        api_key = self.api_edit.text().strip()

        if not input_dir:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Chọn Folder Input."); return
        if not output_dir:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Chọn Folder Output."); return
        if not mapping_dir:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Chọn thư mục ID (Excel)."); return

        self._save_config_from_ui()

        self.progress.setMaximum(100); self.progress.setValue(0)
        self.status_label.setText("Đang chạy..."); self.warn_label.setText("")
        self.result_table.setRowCount(0); self.set_ui_enabled(False)

        self.worker = PipelineThread(input_dir, output_dir, mapping_dir, api_key, self)
        self.worker.progress_changed.connect(self.on_progress_changed)
        self.worker.finished_with_result.connect(self.on_finished_with_result)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    @QtCore.pyqtSlot(int, int, str)
    def on_progress_changed(self, i, total, msg):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(max(i, 0))
        base = Path(str(msg)).name if msg else ""
        self.status_label.setText(f"({i}/{total}) {base}")

    def _tint_row(self, row: int):
        color = QtGui.QColor(255, 245, 200)
        for col in range(self.result_table.columnCount()):
            it = self.result_table.item(row, col)
            if it: it.setBackground(color)

    def _add_result_row(self, rec: dict):
        row = self.result_table.rowCount(); self.result_table.insertRow(row)
        name = Path(rec.get("input") or "").name
        self.result_table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
        st = rec.get("stats", {}) or {}
        it_q = QtWidgets.QTableWidgetItem(str(st.get("questions", 0))); it_q.setTextAlignment(QtCore.Qt.AlignCenter)
        self.result_table.setItem(row, 1, it_q)
        kinds = f"MCQ={st.get('multichoice',0)}, Kprime={st.get('kprime',0)}, SA={st.get('shortanswer',0)}"
        it_k = QtWidgets.QTableWidgetItem(kinds); it_k.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.result_table.setItem(row, 2, it_k)
        imgs = f"{st.get('images_online',0)}/{st.get('images_total',0)}"
        it_i = QtWidgets.QTableWidgetItem(imgs); it_i.setTextAlignment(QtCore.Qt.AlignCenter)
        self.result_table.setItem(row, 3, it_i)

        btn = QtWidgets.QPushButton("Mở chứa XML")
        xml_path = rec.get("output_xml") or ""
        if not xml_path: btn.setEnabled(False)
        btn.clicked.connect(partial(self.open_xml_container, xml_path))
        self.result_table.setCellWidget(row, 4, btn)

        suspect = int(rec.get("flags", {}).get("suspect_names", 0))
        if suspect > 0:
            tip = "Có <name> dạng Qxxx. Sang tab 'Thao tác XML' để cập nhật Category rồi thêm mã đề."
            for col in range(4):
                it = self.result_table.item(row, col)
                if it: it.setToolTip(tip)
            self._tint_row(row)

    @QtCore.pyqtSlot(dict)
    def on_finished_with_result(self, result: dict):
        self.set_ui_enabled(True)
        files = result.get("files", []) or []
        totals = result.get("totals", {}) or {}
        nfiles = len(files)

        self.result_table.setRowCount(0)
        for rec in files: self._add_result_row(rec)
        self.result_table.resizeRowsToContents()

        self.progress.setMaximum(max(nfiles, 1)); self.progress.setValue(max(nfiles, 1))
        self.status_label.setText(f"Hoàn tất {nfiles} file.")
        suspect = int(totals.get("suspect_names", 0))
        self.warn_label.setText("" if suspect == 0 else
            "⚠️ Phát hiện tên dạng Qxxx. Vào tab 'Thao tác XML' → Cập nhật Category (sẽ chuẩn hoá tên) rồi thêm mã đề.")

        QtWidgets.QMessageBox.information(
            self, "Xong",
            "Hoàn tất {} file.\n- Câu hỏi: {}\n- Ảnh online: {}/{}".format(
                nfiles, totals.get("questions", 0),
                totals.get("images_online", 0), totals.get("images_total", 0)
            )
        )

    @QtCore.pyqtSlot(str)
    def on_failed(self, err):
        self.set_ui_enabled(True)
        self.status_label.setText("Bị lỗi.")
        QtWidgets.QMessageBox.critical(self, "Lỗi", err)

    # ================= Tab “Thao tác XML” =================
    def _pick_xml_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Chọn file XML", "", "Moodle XML (*.xml);;Tất cả (*.*)")
        if not files: return
        self._exam_sources = [Path(f) for f in files]
        self.exam_xml_edit.setText(files[0] if len(files)==1 else f"{files[0]} (+{len(files)-1} file)")
        self._scan_and_warn_sources()

    def _pick_xml_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa XML")
        if not d: return
        self._exam_sources = [Path(d)]
        self.exam_xml_edit.setText(d)
        self._scan_and_warn_sources()

    def _collect_xml_files_from_sources(self) -> List[Path]:
        xml_files: List[Path] = []
        for src in getattr(self, "_exam_sources", []):
            if src.is_dir(): xml_files.extend(sorted(src.rglob("*.xml")))
            elif src.is_file() and src.suffix.lower() == ".xml": xml_files.append(src)
        return xml_files

    def _scan_and_warn_sources(self):
        xml_files = self._collect_xml_files_from_sources()
        if not xml_files: self.lbl_xml_hint.setText(""); return
        pat_simple_q = re.compile(r"^\s*Q\d+\s*(\|\s*Mã đề:\s*.+)?$", re.IGNORECASE)
        bad = total = 0
        for xf in xml_files[:200]:
            try:
                tree = ET.parse(str(xf)); root = tree.getroot()
                for q in root.findall(".//question"):
                    name_el = q.find("./name"); text_el = name_el.find("./text") if name_el is not None else None
                    if text_el is None: continue
                    total += 1
                    cur = (text_el.text or "").strip()
                    if pat_simple_q.fullmatch(cur): bad += 1
            except Exception: pass
        self.lbl_xml_hint.setText("" if bad==0 else f"⚠️ {bad}/{total} <name> dạng 'Q001'. Cập nhật Category trước, rồi thêm mã đề.")

    # ---- Action A: Cập nhật Category + chuẩn hoá name = leaf ----
    def _apply_update_category(self):
        if not hasattr(self, "_exam_sources") or not self._exam_sources:
            QtWidgets.QMessageBox.warning(self, "Thiếu nguồn", "Chọn file/thư mục XML trước."); return
        cat_text = (self.category_edit.text() or "").strip()
        if not cat_text:
            QtWidgets.QMessageBox.warning(self, "Thiếu Category", "Nhập chuỗi Category trước khi cập nhật."); return

        xml_files = self._collect_xml_files_from_sources()
        if not xml_files:
            QtWidgets.QMessageBox.information(self, "Không có XML", "Không tìm thấy file *.xml để xử lý."); return

        leaf = self._extract_leaf_category_from_text(cat_text)
        rx_strip_code = re.compile(r"\s*\|\s*Mã đề:\s*.+$", re.IGNORECASE)

        files_changed = 0; names_changed = 0; errors = []
        for xf in xml_files:
            try:
                ET.register_namespace('', '')
                tree = ET.parse(str(xf)); root = tree.getroot()

                # ghi category mới (xoá cũ, chèn mới)
                for node in root.findall("./question[@type='category']"):
                    root.remove(node)
                cat_q = ET.Element("question", attrib={"type": "category"})
                cat_el = ET.SubElement(cat_q, "category")
                text_el = ET.SubElement(cat_el, "text"); text_el.text = cat_text
                root.insert(0, cat_q)

                # chuẩn hoá mọi <name> = leaf (bỏ mọi tail mã đề)
                if leaf:
                    for q in root.findall(".//question"):
                        if q.get("type") == "category": continue
                        name_el = q.find("./name"); te = name_el.find("./text") if name_el is not None else None
                        if te is None: continue
                        cur = (te.text or "").strip()
                        base = rx_strip_code.sub("", cur)  # bỏ tail nếu có
                        if base != leaf:
                            te.text = leaf; names_changed += 1

                tree.write(str(xf), encoding="utf-8", xml_declaration=True); files_changed += 1
            except Exception as e:
                errors.append(f"{xf.name}: {e}")

        msg = f"Đã cập nhật Category và chuẩn hoá tên cho {files_changed}/{len(xml_files)} file."
        msg += f" Số <name> cập nhật: {names_changed}."
        if errors: msg += "\n\nMột số lỗi:\n- " + "\n- ".join(errors[:10])
        QtWidgets.QMessageBox.information(self, "Hoàn tất", msg)

    # ---- Action B: Thêm/Ghi đè mã đề (chỉ tail, không đổi phần tên) ----
    def _apply_assign_examcode(self):
        if not hasattr(self, "_exam_sources") or not self._exam_sources:
            QtWidgets.QMessageBox.warning(self, "Thiếu nguồn", "Chọn file/thư mục XML trước."); return
        code = (self.exam_code_edit.text() or "").strip()
        if not code:
            QtWidgets.QMessageBox.warning(self, "Thiếu mã đề", "Nhập mã đề trước khi thực hiện."); return

        xml_files = self._collect_xml_files_from_sources()
        if not xml_files:
            QtWidgets.QMessageBox.information(self, "Không có XML", "Không tìm thấy file *.xml để xử lý."); return

        rx_strip_code = re.compile(r"\s*\|\s*Mã đề:\s*.+$", re.IGNORECASE)
        files_changed = 0; names_changed = 0; errors = []
        for xf in xml_files:
            try:
                ET.register_namespace('', '')
                tree = ET.parse(str(xf)); root = tree.getroot()
                changed = False
                for q in root.findall(".//question"):
                    if q.get("type") == "category": continue
                    name_el = q.find("./name"); te = name_el.find("./text") if name_el is not None else None
                    if te is None: continue
                    cur = (te.text or "").strip()
                    base = rx_strip_code.sub("", cur)          # giữ nguyên phần tên, bỏ tail cũ
                    new_text = f"{base} | Mã đề: {code}"
                    if new_text != cur:
                        te.text = new_text; names_changed += 1; changed = True
                if changed:
                    tree.write(str(xf), encoding="utf-8", xml_declaration=True); files_changed += 1
            except Exception as e:
                errors.append(f"{xf.name}: {e}")

        msg = f"Đã thêm/ghi đè mã đề cho {files_changed}/{len(xml_files)} file. Số <name> cập nhật: {names_changed}."
        if errors: msg += "\n\nMột số lỗi:\n- " + "\n- ".join(errors[:10])
        QtWidgets.QMessageBox.information(self, "Hoàn tất", msg)

    # ==== helpers ====
    @staticmethod
    def _extract_leaf_category_from_root(root: ET.Element) -> str:
        cat_node = None
        for q in root.findall("./question"):
            if q.get("type") == "category":
                cat_node = q.find("./category/text")
                if cat_node is not None: break
        if cat_node is None: return ""
        return MainUI._extract_leaf_category_from_text(cat_node.text or "")

    @staticmethod
    def _extract_leaf_category_from_text(text: str) -> str:
        if not text: return ""
        parts = [p.strip() for p in text.split("/") if p.strip()]
        return parts[-1] if parts else ""

if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    win = MainUI()
    win.show()
    sys.exit(app.exec_())