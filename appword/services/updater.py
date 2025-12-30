#tự động cập nhật – tuỳ chọn
# # -*- coding: utf-8 -*-
import hashlib, json, os, shutil, subprocess, tempfile, urllib.request
from pathlib import Path

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest().lower()

def check_and_update(version_url: str, installer_url: str, expected_sha256: str = "") -> bool:
    """
    - Tải version.json (nếu thầy muốn) hoặc dùng expected_sha256 truyền vào.
    - Tải installer .exe, kiểm tra sha256, chạy silent /VERYSILENT /NORESTART
    Trả True nếu đã khởi chạy installer (app nên thoát sau khi gọi).
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="mq_update_"))
    try:
        if not expected_sha256:
            with urllib.request.urlopen(version_url, timeout=10) as r:
                meta = json.loads(r.read().decode("utf-8"))
            expected_sha256 = (meta.get("sha256") or "").lower()

        dest = tmpdir / "setup.exe"
        urllib.request.urlretrieve(installer_url, str(dest))

        if expected_sha256:
            calc = sha256_file(dest)
            if calc.lower() != expected_sha256.lower():
                raise RuntimeError(f"SHA256 không khớp.\nExpect: {expected_sha256}\nGot:    {calc}")

        subprocess.Popen([str(dest), "/VERYSILENT", "/NORESTART"], close_fds=True)
        return True
    finally:
        # không xoá tmpdir ngay để tránh xoá file đang chạy; để hệ thống dọn sau.
        pass
