# -*- coding: utf-8 -*-
from __future__ import annotations
import io, os, sys, json, time, tempfile, math
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception:
    Image = None
try:
    import requests
except Exception:
    requests = None

# ================= HELPER: ĐỌC CONFIG =================
def get_app_path():
    """Lấy đường dẫn thư mục chứa file .exe (hoặc file script)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_config_api_key():
    """Đọc API Key từ file settings.json nằm cạnh file .exe"""
    try:
        # File nằm ở: <Folder chứa App>/configs/settings.json
        config_path = os.path.join(get_app_path(), "configs", "settings.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("api_key", "").strip()
                if key: return key
                # Fallback: có thể lưu ở last_api_key (tùy code main_ui lưu tên gì)
                return data.get("last_api_key", "").strip()
    except Exception:
        pass
    return ""
# ======================================================

@dataclass
class UploadResult:
    ok: bool
    url: Optional[str] = None
    error: Optional[str] = None
    provider: str = "imgbb"
    status_code: Optional[int] = None

class ImageUploader:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "imgbb",
        timeout: int = 60,
        max_retries: int = 4,
        backoff_factor: float = 1.8,
        verbose: bool = True,
        # compression knobs (overridable by env)
        max_side: Optional[int] = None,
        min_side: Optional[int] = None,
        target_bytes: Optional[int] = None,
    ):
        self.provider = provider.lower().strip()
        
        # --- LOGIC LẤY KEY MỚI ---
        # Ưu tiên 1: Key truyền trực tiếp vào hàm
        # Ưu tiên 2: Key trong file settings.json (Người dùng nhập)
        # Ưu tiên 3: Key trong biến môi trường (Cho Dev)
        self.api_key = api_key or get_config_api_key() or os.getenv("IMGBB_API_KEY") or ""
        # -------------------------

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.verbose = verbose

        # env overrides
        env_max_side = os.getenv("APPWORD_MAX_SIDE")
        env_min_side = os.getenv("APPWORD_MIN_SIDE")
        env_target_kb = os.getenv("APPWORD_TARGET_KB")

        self.max_side = int(max_side or (int(env_max_side) if env_max_side else 900))
        self.min_side = int(min_side or (int(env_min_side) if env_min_side else 600))
        self.target_bytes = int(target_bytes or ((int(env_target_kb) if env_target_kb else 120) * 1024))

    # ---------- utils ----------
    def _v(self, *args):
        if self.verbose: print("[uploader]", *args)

    def upload_url_or_path(self, s: str) -> UploadResult:
        if not s or str(s).lower().startswith(("http://", "https://", "file://")):
            return UploadResult(ok=True, url=s, provider="passthrough")
        p = os.path.abspath(s)
        if not os.path.exists(p):
            msg = f"File not found: {p}"
            self._v(msg)
            return UploadResult(ok=False, url=None, error=msg, provider="local")
        return self.upload_path(p)

    def upload_path(self, image_path: str, suggested_name: Optional[str] = None) -> UploadResult:
        try:
            pil = self._open_as_pil(image_path)
            name = suggested_name or os.path.basename(image_path) or "image.png"
            return self._upload_or_local(pil, name)
        except Exception as e:
            self._v("Open image failed:", e)
            if Image is not None:
                try:
                    pil = self._open_as_pil(image_path)
                    url = self._save_local_temp(pil, suggested_name or os.path.basename(image_path) or "image.png")
                    return UploadResult(ok=False, url=url, error=str(e), provider="local")
                except Exception as e2:
                    return UploadResult(ok=False, url=None, error=f"{e} | {e2}", provider="local")
            return UploadResult(ok=False, url=None, error=str(e), provider="local")

    def upload_pil(self, pil_img, suggested_name: str = "image.png") -> UploadResult:
        try:
            return self._upload_or_local(pil_img, suggested_name)
        except Exception as e:
            try:
                url = self._save_local_temp(pil_img, suggested_name)
                return UploadResult(ok=False, url=url, error=str(e), provider="local")
            except Exception as e2:
                return UploadResult(ok=False, url=None, error=f"{e} | {e2}", provider="local")

    # ---------- core ----------
    def _upload_or_local(self, pil_img, suggested_name: str) -> UploadResult:
        pil_img = self._prepare_for_web(pil_img)
        data_bytes, mime, out_name = self._encode_until_target(pil_img, suggested_name, self.target_bytes)

        # Imgbb trước
        if self.api_key and requests:
            try:
                url, status = self._upload_imgbb_bytes(data_bytes, out_name, mime)
                return UploadResult(ok=True, url=url, provider="imgbb", status_code=status)
            except Exception as e:
                self._v("ImgBB upload failed → fallback Catbox:", e)

        # Catbox fallback
        if requests:
            try:
                url = self._upload_catbox_bytes(data_bytes, out_name, mime)
                return UploadResult(ok=True, url=url, provider="catbox", status_code=200)
            except Exception as e:
                self._v("Catbox upload failed → save local:", e)

        # Local cuối cùng
        try:
            url = self._save_local_temp(pil_img, suggested_name)
            return UploadResult(ok=False, url=url, provider="local", error="Upload failed → saved locally")
        except Exception as e:
            return UploadResult(ok=False, url=None, provider="local", error=str(e))

    # ---------- prepare & encode ----------
    def _open_as_pil(self, path: str):
        if Image is None: raise RuntimeError("Missing 'Pillow'")
        im = Image.open(path)
        im.load()
        return im

    def _prepare_for_web(self, im):
        if Image is None: raise RuntimeError("Missing 'Pillow'")
        if im.mode in ("P", "LA"): im = im.convert("RGBA")
        if im.mode == "CMYK": im = im.convert("RGB")
        # co về max_side trước
        im = self._resize_to_max(im, self.max_side)
        return im

    def _resize_to_max(self, im, max_side: int):
        w, h = im.size
        if max(w, h) <= max_side: return im
        scale = max_side / float(max(w, h))
        nw, nh = max(1, int(w*scale)), max(1, int(h*scale))
        return im.resize((nw, nh), Image.LANCZOS)

    def _resize_by_factor(self, im, factor: float):
        w, h = im.size
        nw, nh = max(1, int(w*factor)), max(1, int(h*factor))
        return im.resize((nw, nh), Image.LANCZOS)

    def _is_line_art(self, im) -> bool:
        try:
            sm = im.convert("RGB").resize((max(1, im.width//8), max(1, im.height//8)), Image.BILINEAR)
            colors = sm.getcolors(maxcolors=65536)
            uniq = len(colors) if colors else 999999
            # ít màu + nhiều nền trắng → coi như line-art
            whiteish = sum(1 for c in (colors or []) if max(c[1]) > 240)
            return (uniq < 260) or (whiteish > (0.5 * (len(colors) if colors else 1)))
        except Exception:
            return False

    def _encode_until_target(self, im, suggested_name: str, target_bytes: int) -> Tuple[bytes, str, str]:
        """Nén lặp: nếu chưa đạt target thì tiếp tục giảm chất lượng/kích thước (tối thiểu min_side)."""
        if Image is None: raise RuntimeError("Missing 'Pillow'")
        has_alpha = ("A" in im.getbands())
        line_art = self._is_line_art(im)

        # bộ mã hoá
        def to_rgb_white(img):
            if "A" not in img.getbands(): return img.convert("RGB")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            return bg

        # thử PNG palette mạnh cho line-art
        if line_art:
            base = (im.convert("RGBA") if has_alpha else im.convert("RGB"))
            for colors in (128, 64, 32, 16):
                pal = base.convert("P", palette=Image.MEDIANCUT, colors=colors, dither=Image.FLOYDSTEINBERG)
                b = io.BytesIO()
                pal.save(b, format="PNG", optimize=True)
                data = b.getvalue()
                if len(data) <= target_bytes:
                    return data, "image/png", self._force_ext(suggested_name, ".png")
            # nếu chưa đạt: chuyển về grayscale JPEG và đi tiếp vòng lặp ở dưới
            im = ImageOps.grayscale(to_rgb_white(im))

        # JPEG lặp chất lượng + nếu cần giảm kích thước
        q = 80
        best = None
        cur = to_rgb_white(im) if im.mode not in ("L", "RGB") else im
        while True:
            # encode với một dải chất lượng
            qq = q
            while qq >= 30:
                b = io.BytesIO()
                cur.save(b, format="JPEG", quality=qq, optimize=True, progressive=True, subsampling="4:2:0")
                data = b.getvalue()
                best = (data, "image/jpeg", self._force_ext(suggested_name, ".jpg"))
                if len(data) <= target_bytes:
                    return best
                qq -= 8
            # nếu vẫn lớn → giảm kích thước 10%
            if max(cur.size) <= self.min_side:
                # hết cỡ giảm rồi, trả best hiện có
                return best
            cur = self._resize_by_factor(cur, 0.90)

    def _force_ext(self, name: str, ext: str) -> str:
        base, _ = os.path.splitext(os.path.basename(name) or "image")
        return f"{base}{ext}"

    # ---------- uploaders ----------
    def _upload_imgbb_bytes(self, data_bytes: bytes, filename: str, mime: str):
        if not requests: raise RuntimeError("Missing 'requests'")
        if not self.api_key: raise RuntimeError("Missing IMGBB_API_KEY")
        url = "https://api.imgbb.com/1/upload"
        files = {"image": (filename, data_bytes, mime)}
        data = {"key": self.api_key}
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                r = requests.post(url, data=data, files=files, timeout=self.timeout)
                status = r.status_code
                try:
                    js = r.json()
                except Exception:
                    js = {}
                if status == 200 and js.get("success"):
                    direct = js.get("data", {}).get("image", {}).get("url") or js.get("data", {}).get("url")
                    if not direct:
                        raise RuntimeError("No direct image url in response.")
                    return direct, status
                self._v(f"ImgBB HTTP {status}: {js or r.text}")
                if status in (408, 429, 500, 502, 503, 504):
                    last_err = f"HTTP {status}"
                    time.sleep(self.backoff_factor * attempt); continue
                raise RuntimeError(f"Upload failed (status {status}): {js or r.text}")
            except Exception as e:
                last_err = str(e)
                self._v(f"Attempt {attempt} error:", last_err)
                time.sleep(self.backoff_factor * attempt)
        raise RuntimeError(f"ImgBB upload failed after retries: {last_err}")

    def _upload_catbox_bytes(self, data_bytes: bytes, filename: str, mime: str) -> str:
        if not requests: raise RuntimeError("Missing 'requests'")
        url = "https://catbox.moe/user/api.php"
        files = {"fileToUpload": (filename, data_bytes, mime)}
        data = {"reqtype": "fileupload"}
        resp = requests.post(url, data=data, files=files, timeout=self.timeout)
        if resp.status_code == 200 and resp.text.startswith("http"):
            return resp.text.strip()
        raise RuntimeError(f"Catbox error {resp.status_code}: {resp.text}")

    # ---------- local fallback ----------
    def _save_local_temp(self, pil_img, suggested_name: str) -> str:
        if Image is None: raise RuntimeError("Missing 'Pillow'")
        tmp = os.path.join(tempfile.gettempdir(), "appword_images")
        os.makedirs(tmp, exist_ok=True)
        base, _ = os.path.splitext(os.path.basename(suggested_name) or "image")
        out = os.path.join(tmp, f"{base}_{int(time.time()*1000)}.jpg")
        pil_img = pil_img.convert("RGB")
        pil_img.save(out, format="JPEG", quality=75, optimize=True, progressive=True, subsampling="4:2:0")
        return "file://" + out