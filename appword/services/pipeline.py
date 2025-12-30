# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Callable, Optional, Tuple

# --- Core steps ---
from appword.core.parser import parse_docx_to_json
from appword.core.enricher import enrich_json_with_mapping
from appword.core.exporter import build_quiz_from_json

# --- Image upload/attach ---
from appword.services.uploader import ImageUploader
from appword.tools.post_upload_links import attach_image_links


# ========== Small IO helpers ==========
def _read_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _safe_progress(cb: Optional[Callable[[int, int, str], None]], i: int, total: int, msg: str):
    try:
        if cb:
            cb(i, total, msg)
    except Exception:
        # never let UI crash because of a bad callback
        pass

def _file_ok(p: Optional[Path]) -> bool:
    try:
        return bool(p and p.exists() and p.stat().st_size > 0)
    except Exception:
        return False


# ========== DOCX pipeline ==========
def _process_one_docx(
    docx: Path,
    per_out_dir: Path,
    uploader: ImageUploader,
    mapping_dir: Optional[str],
) -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    """
    Xử lý 1 file .docx:
      .docx -> questionsTF.json -> (enrich) -> attach *_url -> questionsTF.uploaded.json -> moodle.xml
    Trả về: (uploaded_json_path | None, xml_path | None, error | None)
    """
    try:
        per_out_dir.mkdir(parents=True, exist_ok=True)

        # 1) DOCX -> JSON
        print(f"[DOCX] Parse: {docx}")
        raw_json_path = Path(parse_docx_to_json(str(docx), output_dir=str(per_out_dir)))
        if not _file_ok(raw_json_path):
            raise RuntimeError(
                f"Parser KHÔNG sinh JSON cho '{docx.name}'. "
                f"Kiểm tra lại định dạng docx. Dự kiến: {per_out_dir/'questionsTF.json'}"
            )
        print(f"[DOCX]   ✓ JSON: {raw_json_path.name} ({raw_json_path.stat().st_size} bytes)")

        # 2) Enrich (optional)
        json_path = raw_json_path
        if mapping_dir:
            print(f"[DOCX] Enrich với mapping_dir={mapping_dir!r}")
            json_path = Path(
                enrich_json_with_mapping(
                    str(raw_json_path),
                    mapping_dir,
                    json_out=None,
                    overwrite=True,
                    log=True,
                )
            )
            if not _file_ok(json_path):
                raise RuntimeError(
                    f"Enricher chạy xong nhưng KHÔNG thấy JSON: {json_path}"
                )
            print(f"[DOCX]   ✓ Enriched JSON: {json_path.name}")

        # 3) Upload & attach *_url
        print(f"[DOCX] Upload & attach image links…")
        data = _read_json(json_path)
        data = attach_image_links(data, uploader)
        uploaded_json = json_path.with_suffix(".uploaded.json")
        _write_json(uploaded_json, data)
        if not _file_ok(uploaded_json):
            raise RuntimeError(
                f"Không tạo được file uploaded JSON: {uploaded_json}"
            )

        # 4) Build XML
        xml_out = per_out_dir / "moodle.xml"
        build_quiz_from_json(str(uploaded_json), xml_out=str(xml_out))
        if not _file_ok(xml_out):
            raise RuntimeError(
                f"Exporter báo thành công nhưng KHÔNG thấy XML: {xml_out}"
            )

        # 5) Nhặt thống kê nhanh (để nhìn log)
        try:
            qs = [x for x in data if isinstance(x, dict) and x.get("question_type")]
        except Exception:
            qs = []
        mc = sum(1 for q in qs if q.get("question_type") == "multichoice")
        kp = sum(1 for q in qs if q.get("question_type") in ("kprime", "truefalse", "tf", "true_false"))
        sa = sum(1 for q in qs if q.get("question_type") == "shortanswer")

        print(
            f"[DOCX] OK {docx.name} -> {uploaded_json.name}, XML={xml_out.name} | "
            f"MCQ: {mc} | KPrime: {kp} | SA: {sa}"
        )
        return uploaded_json, xml_out, None

    except Exception as e:
        print(f"[DOCX] FAIL {docx} :: {e}")
        return None, None, str(e)


# ========== JSON pipeline ==========
def _process_one_json(
    src_json: Path,
    out_root: Path,
    in_root: Path,
    uploader: ImageUploader
) -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    """
    JSON mode: mirror cấu trúc input
      <out_root>/<relative_path>.uploaded.json và .xml
    """
    try:
        rel = src_json.relative_to(in_root)
        out_json = (out_root / rel).with_suffix(".uploaded.json")
        out_xml  = (out_root / rel).with_suffix(".xml")

        print(f"[JSON] Attach & Export: {src_json}")
        if not _file_ok(src_json):
            raise RuntimeError(f"File JSON rỗng/không tồn tại: {src_json}")

        data = _read_json(src_json)
        data = attach_image_links(data, uploader)
        _write_json(out_json, data)
        if not _file_ok(out_json):
            raise RuntimeError(f"Không tạo được uploaded JSON: {out_json}")

        build_quiz_from_json(str(out_json), xml_out=str(out_xml))
        if not _file_ok(out_xml):
            raise RuntimeError(f"Exporter KHÔNG sinh XML: {out_xml}")

        # Thống kê nhanh
        try:
            qs = [x for x in data if isinstance(x, dict) and x.get("question_type")]
        except Exception:
            qs = []
        mc = sum(1 for q in qs if q.get("question_type") == "multichoice")
        kp = sum(1 for q in qs if q.get("question_type") in ("kprime", "truefalse", "tf", "true_false"))
        sa = sum(1 for q in qs if q.get("question_type") == "shortanswer")

        print(f"[JSON] OK {src_json.name} -> {out_json.name} | XML: {out_xml.name} | MCQ:{mc} KPrime:{kp} SA:{sa}")
        return out_json, out_xml, None

    except Exception as e:
        print(f"[JSON] FAIL {src_json} :: {e}")
        return None, None, str(e)


# ========== Public API ==========
def run_pipeline(
    input_folder: str,
    output_folder: str,
    api_key: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    mapping_dir: Optional[str] = None,
) -> int:
    """
    DOCX mode:
        *.docx (bỏ qua ~$.docx) -> parse -> (enrich) -> attach *_url -> *.uploaded.json -> moodle.xml
    JSON mode:
        questionsTF.json -> attach *_url -> *.uploaded.json -> .xml (mirror cây)
    Trả về: tổng số file INPUT đã thử xử lý (để UI hiển thị "Hoàn tất N file").
    """
    in_dir = Path(input_folder)
    out_dir = Path(output_folder)

    if not in_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục Input: {in_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    # API key cho uploader (ưu tiên tham số truyền vào)
    if api_key:
        os.environ["IMGBB_API_KEY"] = api_key
    uploader = ImageUploader(api_key=os.getenv("IMGBB_API_KEY"), verbose=True)

    # --- DOCX mode ---
    docxs = sorted(
        p for p in in_dir.rglob("*.docx")
        if not p.name.startswith("~$")  # bỏ file tạm của MS Word
    )
    if docxs:
        total = len(docxs)
        print(f"[RUN] DOCX mode | {total} file(s) | input={in_dir} -> output={out_dir}")
        for i, docx in enumerate(docxs, 1):
            per = out_dir / docx.stem
            _safe_progress(progress_cb, i - 1, total, f"START DOCX {docx}")
            uploaded_json, xml_out, err = _process_one_docx(docx, per, uploader, mapping_dir)
            if err:
                _safe_progress(progress_cb, i, total, f"FAIL  DOCX {docx} :: {err}")
            else:
                _safe_progress(progress_cb, i, total, f"OK    DOCX {docx} -> {uploaded_json} | XML: {xml_out}")
        _safe_progress(progress_cb, total, total, f"SUMMARY DOCX :: TOTAL={total}")
        return total

    # --- JSON mode (chỉ xử lý questionsTF.json; bỏ qua .uploaded.json) ---
    jsons = [
        p for p in in_dir.rglob("*.json")
        if p.name.endswith("questionsTF.json")
        and not p.name.endswith(".uploaded.json")
        and not p.name.startswith("~$")
    ]
    if not jsons:
        raise FileNotFoundError("Không tìm thấy file .docx hoặc questionsTF.json nào trong Input.")

    total = len(jsons)
    print(f"[RUN] JSON mode | {total} file(s) | input={in_dir} -> output={out_dir}")
    for i, jp in enumerate(jsons, 1):
        _safe_progress(progress_cb, i - 1, total, f"START JSON {jp}")
        out_json, out_xml, err = _process_one_json(jp, out_dir, in_dir, uploader)
        if err:
            _safe_progress(progress_cb, i, total, f"FAIL  JSON {jp} :: {err}")
        else:
            _safe_progress(progress_cb, i, total, f"OK    JSON {jp} -> {out_json} | XML: {out_xml}")

    _safe_progress(progress_cb, total, total, f"SUMMARY JSON :: TOTAL={total}")
    return total
