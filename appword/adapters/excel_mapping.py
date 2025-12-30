# appword/adapters/excel_mapping.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
import re, unicodedata

# ---------- Chuẩn hoá chuỗi ----------
def _strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def _norm_ws_upper(s: str) -> str:
    """Bỏ khoảng trắng, upper (giữ dấu chấm)."""
    return re.sub(r"\s+", "", (s or "")).upper()

def _norm_alnum_upper(s: str) -> str:
    """Bỏ dấu, bỏ mọi ký tự không [0-9A-Z], upper (loại chấm)."""
    s = _strip_accents(s or "").upper()
    return re.sub(r"[^0-9A-Z]", "", s)

def _norm_code_variants(s: str) -> set[str]:
    """Sinh các biến thể để so khớp linh hoạt."""
    raw = (s or "").strip()
    nodot = raw.replace(".", "")
    return {
        raw, nodot,
        _norm_ws_upper(raw), _norm_ws_upper(nodot),
        _norm_alnum_upper(raw), _norm_alnum_upper(nodot),
    }

# ---------- Đọc Excel ----------
def _read_one_excel(p: Path) -> pd.DataFrame:
    df = pd.read_excel(p, sheet_name=0, header=None, dtype=str)
    while df.shape[1] < 3:
        df[df.shape[1]] = ""
    df = df.iloc[:, :3]
    df.columns = ["A", "B", "C"]
    for c in ["A", "B", "C"]:
        df[c] = df[c].fillna("").astype(str).str.strip()

    # các cột chuẩn hoá để tra cứu
    df["A_WS_UP"] = df["A"].apply(_norm_ws_upper)
    df["A_ALNUM_UP"] = df["A"].apply(_norm_alnum_upper)
    df["A_NODOT"] = df["A"].str.replace(".", "", regex=False)
    df["A_NODOT_ALNUM_UP"] = df["A_NODOT"].apply(_norm_alnum_upper)
    return df

def load_mapping_dir(dir_path: str) -> pd.DataFrame:
    d = Path(dir_path)
    if not d.exists():
        raise FileNotFoundError(f"Không thấy thư mục mapping: {dir_path}")
    frames = []
    for pat in ("*.xlsx", "*.xls"):
        for p in sorted(d.glob(pat)):
            try:
                frames.append(_read_one_excel(p))
            except Exception:
                # bỏ qua file lỗi/không phải excel chuẩn
                continue
    if not frames:
        return pd.DataFrame(columns=[
            "A", "B", "C", "A_WS_UP", "A_ALNUM_UP",
            "A_NODOT", "A_NODOT_ALNUM_UP"
        ])
    return pd.concat(frames, ignore_index=True)

# ---------- Tách base code ----------
def _base_code_from_qid(qid: str) -> str:
    """
    'TO12.04.1.F02.a' -> 'TO12.04.1.F02';
    nếu phần cuối không phải một hậu tố chữ, giữ nguyên.
    """
    qid = (qid or "").strip()
    if not qid:
        return ""
    parts = qid.split(".")
    if len(parts) >= 2 and parts[-1].isalpha():
        return ".".join(parts[:-1])
    return qid

# ---------- Lookup chính ----------
# def lookup_name_category(question_id: str, df: "pd.DataFrame") -> Tuple[Optional[str], Optional[str]]:
#     """
#     Trả về (question_name, question_category) nếu tìm thấy hàng khớp cột A.
#     Quy tắc đặt tên:
#       - question_name     = "{qid} {col_b}".strip()
#       - question_category = "{col_c}/{question_name}" nếu C có dữ liệu,
#                             ngược lại = question_name (không có '/').
#     Không tìm thấy -> (None, None).
#     """
#     if df is None or df.empty:
#         return None, None

#     qid = (question_id or "").strip()
#     if not qid:
#         return None, None

#     base = _base_code_from_qid(qid)
#     base_vars = _norm_code_variants(base)
#     qid_vars  = _norm_code_variants(qid)

#     # 1) So khớp raw: A == qid, rồi A == base
#     hit = df[df["A"] == qid]
#     if hit.empty:
#         hit = df[df["A"] == base]

#     # 2) So khớp normalized & không dấu chấm
#     if hit.empty:
#         cond = (
#             df["A_WS_UP"].isin({ _norm_ws_upper(qid), _norm_ws_upper(base) }) |
#             df["A_ALNUM_UP"].isin({ _norm_alnum_upper(qid), _norm_alnum_upper(base) }) |
#             df["A_NODOT"]          .isin({ qid.replace(".", ""), base.replace(".", "") }) |
#             df["A_NODOT_ALNUM_UP"] .isin({ _norm_alnum_upper(qid.replace(".", "")),
#                                            _norm_alnum_upper(base.replace(".", "")) })
#         )
#         hit = df[cond]

#     # 3) So khớp theo 13..15 ký tự đầu (hai chiều, raw & normalized)
#     if hit.empty:
#         prefixes = set()
#         for k in (13, 14, 15):
#             prefixes.add(base[:k]); prefixes.add(base.replace(".", "")[:k])
#         pref_norms = set()
#         for c in list(prefixes):
#             pref_norms |= _norm_code_variants(c)

#         def _prefix_two_way(a: str) -> bool:
#             if not a:
#                 return False
#             pool = _norm_code_variants(a)
#             # giao với prefixes hoặc variants
#             if pool & prefixes: return True
#             if pool & pref_norms: return True
#             # startswith hai chiều trên dạng ALNUM_UP
#             an = _norm_alnum_upper(a)
#             for c in prefixes:
#                 if an.startswith(_norm_alnum_upper(c)) or _norm_alnum_upper(c).startswith(an):
#                     return True
#             return False

#         tmp = df[df["A"].apply(_prefix_two_way)]
#         if not tmp.empty:
#             hit = tmp

#     # 4) Prefix hai chiều với base (raw & normalized)
#     if hit.empty:
#         tmp = df[df["A"].apply(lambda a: base.startswith(str(a)) or str(a).startswith(base))]
#         if not tmp.empty:
#             hit = tmp
#     if hit.empty:
#         base_al = _norm_alnum_upper(base)
#         tmp = df[df["A_ALNUM_UP"].apply(lambda a: base_al.startswith(str(a)) or str(a).startswith(base_al))]
#         if not tmp.empty:
#             hit = tmp

#     if hit.empty:
#         return None, None

#     row = hit.iloc[0]
#     col_b = (row.get("B") or "").strip()
#     col_c = (row.get("C") or "").strip()

#     qname = f"{qid} {col_b}".strip()
#     qcat  = f"{col_c}/{qname}".strip() if col_c else qname
#     return qname, qcat

def lookup_name_category(question_id: str, df: "pd.DataFrame") -> Tuple[Optional[str], Optional[str]]:
    """
    Tìm theo mã:
      - base = question_id bỏ hậu tố chữ (VD: TO12.04.1.F02.a -> TO12.04.1.F02)
      - Ứng viên = các dòng A == base hoặc A bắt đầu bằng base
      - Ưu tiên chọn dòng có C không rỗng/không "0"
    Trả về (question_name, question_category) hoặc (None, None).
    """
    if df is None or df.empty:
        return None, None

    qid = (question_id or "").strip()
    if not qid:
        return None, None

    base = _base_code_from_qid(qid)

    # Tập ứng viên: exact + startswith (giữ nguyên thứ tự xuất hiện trong các file)
    exact = df[df["A"] == base]
    starts = df[df["A"].str.startswith(base)]
    if exact.empty and starts.empty:
        return None, None
    candidates = pd.concat([exact, starts], ignore_index=True)

    # Ưu tiên C có giá trị (không rỗng, không "0")
    c_series = candidates["C"].astype(str).str.strip()
    non_empty_c = candidates[(c_series != "") & (c_series != "0")]

    row = (non_empty_c.iloc[0] if not non_empty_c.empty else candidates.iloc[0])

    col_b = str(row.get("B") or "").strip()
    col_c = str(row.get("C") or "").strip()
    if col_c == "0":
        col_c = ""  # xem như trống

    qname = f"{qid} {col_b}".strip()
    qcat = f"{col_c}/{qname}".strip() if col_c else None

    return qname, qcat
