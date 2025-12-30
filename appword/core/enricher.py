# -*- coding: utf-8 -*-
from __future__ import annotations
import json, csv
from pathlib import Path
from typing import Optional

from appword.adapters.excel_mapping import load_mapping_dir, lookup_name_category, _base_code_from_qid

def enrich_json_with_mapping(
    json_path: str,
    mapping_dir: str,
    json_out: Optional[str] = None,
    overwrite: bool = True,
    log: bool = True,
) -> str:
    """
    - Đọc JSON câu hỏi.
    - Tìm tên & category từ Excel theo question_id.
    - Ghi lại JSON (đè hoặc ra file mới).
    - Nếu log=True, ghi file CSV 'enrich_log.csv' cạnh JSON để dễ debug.
    """
    p = Path(json_path)
    data = json.loads(p.read_text(encoding="utf-8"))

    df = load_mapping_dir(mapping_dir)

    # file log
    log_rows = []
    log_header = ["index", "qid", "base", "matched",
                  "colB_used_in_name", "colC_used_in_category",
                  "old_name", "old_category", "new_name", "new_category"]

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        if "question_type" not in item:
            continue

        qid  = str(item.get("question_id", "")).strip()
        base = _base_code_from_qid(qid)

        old_name = item.get("question_name", "") or ""
        old_cat  = item.get("question_category", "") or ""

        new_name, new_cat = None, None
        col_b, col_c = "", ""

        # lookup
        hit_name, hit_cat = lookup_name_category(qid, df)
        if hit_name:
            new_name = hit_name
            # rút cột B/C thực sự để log
            try:
                # hit_name = f"{qid} {B}"
                col_b = hit_name[len(qid):].strip()
            except Exception:
                col_b = ""

        if hit_cat:
            new_cat = hit_cat
            # hit_cat = f"{C}/{name}" hoặc = name nếu C rỗng
            if "/" in hit_cat:
                col_c = hit_cat.split("/", 1)[0].strip()

        # cập nhật item
        if new_name and (overwrite or not old_name):
            item["question_name"] = new_name
        else:
            new_name = item.get("question_name", old_name)

        # chỉ set category nếu tìm được C khác rỗng
        if new_cat and ("/" in new_cat):
            if overwrite or not old_cat:
                item["question_category"] = new_cat
        else:
            # không động vào category nếu Excel không có C
            if not item.get("question_category"):
                # giữ nguyên (để rỗng); KHÔNG đặt = name để tránh sai
                item["question_category"] = ""

        # ghi log
        if log:
            log_rows.append([
                idx+1, qid, base,
                "YES" if (hit_name or hit_cat) else "NO",
                col_b, col_c, old_name, old_cat,
                item.get("question_name",""), item.get("question_category","")
            ])

    # xuất JSON
    out = Path(json_out) if json_out else p
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # xuất log CSV
    if log:
        log_file = out.with_name("enrich_log.csv")
        with log_file.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(log_header)
            w.writerows(log_rows)

    return str(out)
