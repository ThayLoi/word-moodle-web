# -*- coding: utf-8 -*-
import json
import os
import re as _re
from pathlib import Path
import html  # <-- đã có

from appword.moodle_questions.MoodleQuiz import MoodleQuiz
from appword.moodle_questions.MultiChoiceQuestion import MultiChoiceQuestion
from appword.moodle_questions.ShortAnswerQuestion import ShortAnswerQuestion
from appword.moodle_questions.ChoiceTFQuestion import ChoiceTFQuestion

# NEW: dùng uploader để lấy URL ảnh (ImgBB / fallback file://)
from appword.services.uploader import ImageUploader


# ========= Helpers chung =========
def _get_opt_text(opt) -> str:
    return (
        (opt or {}).get("option_text")
        or (opt or {}).get("text")
        or (opt or {}).get("answer")
        or (opt or {}).get("value")
        or str(opt)
    )

def _norm_category(s):
    if s is None:
        return None
    ss = str(s).strip()
    if not ss or ss == "0":
        return None
    return ss

def _is_url(s: str) -> bool:
    if not s:
        return False
    ss = str(s).strip().lower()
    return ss.startswith(("http://", "https://", "file://"))

def _img_html(src: str, alt: str = "") -> str:
    if not src:
        return ""
    # khối ảnh căn giữa, chiều rộng auto theo Moodle
    return f'<div style="text-align:center;margin:8px 0"><img src="{src}" alt="{html.escape(alt or "")}"></div>'


# ========= NEW: helpers render BẢNG vào HTML =========
def _render_table_html(tbl: dict) -> str:
    """
    tbl = {
      "headers": ["h1","h2",...],   # (optional)
      "rows": [ ["r1c1","r1c2",...], ... ]
    }
    Trả về <table> inline-style tương thích Moodle.
    """
    if not isinstance(tbl, dict):
        return ""
    headers = tbl.get("headers") or []
    rows = tbl.get("rows") or []

    parts = []
    parts.append('<div style="overflow-x:auto;margin:8px 0;">')
    parts.append('<table style="border-collapse:collapse;width:100%;max-width:720px;margin:auto;" border="1" cellpadding="6">')

    if headers:
        parts.append("<thead><tr>")
        for h in headers:
            parts.append(
                f"<th style='text-align:center;font-weight:600;background:#f5f5f5'>{html.escape(str(h))}</th>"
            )
        parts.append("</tr></thead>")

    if rows:
        parts.append("<tbody>")
        for r in rows:
            parts.append("<tr>")
            for c in r:
                parts.append(f"<td style='text-align:center'>{html.escape(str(c))}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")

    parts.append("</table></div>")
    return "".join(parts)


def _render_tables_block(tables: list) -> str:
    """Nhận list các bảng (mỗi bảng là dict như trên) → ghép lại HTML, bỏ qua bảng lỗi cấu trúc."""
    if not tables:
        return ""
    html_tables = []
    for t in tables:
        try:
            html_tables.append(_render_table_html(t))
        except Exception:
            continue
    return "".join(html_tables)


# ======== Bắt Key / Trả lời (shortanswer) ========
_KEY_PAT = _re.compile(r"<\s*Key\s*=\s*([-+]?\d+(?:[.,]\d+)?)\s*>", flags=_re.I)
_TRALOI_PAT = _re.compile(r"Tr(?:ả|a)\s*l(?:ờ|o)i\s*:\s*([-+]?\d+(?:[.,]\d+)?)", flags=_re.I)

def _dedupe_variants(num_str: str):
    """Sinh các biến thể số thập phân chấp nhận ('.' và ',') và bỏ dấu '+' nếu có."""
    s = (num_str or "").strip()
    if not s:
        return []
    if _re.fullmatch(r"[-+]?\d+", s):
        return [s.lstrip("+")]
    dot = s.replace(",", ".")
    comma = s.replace(".", ",")
    out = []
    for v in (dot.lstrip("+"), comma.lstrip("+")):
        if v not in out:
            out.append(v)
    return out

def _extract_shortanswer_key_and_clean_text(qtext: str, explanation_text: str):
    """
    Trả về (answers:list[str], cleaned_qtext:str).
    Ưu tiên <Key=...> trong qtext; sau đó 'Trả lời: ...' trong lời giải.
    """
    answers = []
    cleaned_qtext = qtext or ""

    m = _KEY_PAT.search(cleaned_qtext)
    if m:
        answers = _dedupe_variants(m.group(1))
        cleaned_qtext = _KEY_PAT.sub("", cleaned_qtext)

    if not answers and explanation_text:
        mt = _TRALOI_PAT.search(explanation_text)
        if mt:
            answers = _dedupe_variants(mt.group(1))

    return answers, cleaned_qtext.strip()


# ========= NEW: gắn link URL vào JSON (không xóa local) =========
def _upload_one(uploader: ImageUploader, p: str) -> str:
    """Trả về URL (http/https/file://). Nếu p đã là URL → trả nguyên, nếu là path local → upload."""
    if not p:
        return ""
    if _is_url(p):
        return p
    res = uploader.upload_url_or_path(p)
    return res.url or p

def _attach_links_in_question(q: dict, uploader: ImageUploader) -> dict:
    # question_image → question_image_url
    qi = q.get("question_image")
    if isinstance(qi, str) and qi.strip():
        q["question_image_url"] = _upload_one(uploader, qi)

    # options[*].option_image → option_image_url
    for opt in (q.get("options") or []):
        if isinstance(opt, dict):
            oi = opt.get("option_image")
            if isinstance(oi, str) and oi.strip():
                opt["option_image_url"] = _upload_one(uploader, oi)

    # explanation.image → explanation.image_url
    exp = q.get("explanation")
    if isinstance(exp, dict):
        exi = exp.get("image")
        if isinstance(exi, str) and exi.strip():
            exp["image_url"] = _upload_one(uploader, exi)
    return q

def _attach_links(data, uploader: ImageUploader):
    if isinstance(data, dict):
        return _attach_links_in_question(data, uploader)
    if isinstance(data, list):
        return [_attach_links_in_question(x, uploader) if isinstance(x, dict) else x for x in data]
    return data


# ========= Hàm chính =========
def build_quiz_from_json(json_file: str, xml_out: str = "output_questions/moodle.xml") -> str:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # NEW: gắn URL ảnh vào dữ liệu (bổ sung *_url, KHÔNG thay trường local)
    uploader = ImageUploader(api_key=os.getenv("IMGBB_API_KEY"))
    data = _attach_links(data, uploader)

    quiz = MoodleQuiz()
    count = {"multichoice": 0, "kprime": 0, "shortanswer": 0}

    # Chấp nhận root là list hoặc dict 1 câu
    items = data if isinstance(data, list) else [data]

    for q in items:
        if not isinstance(q, dict) or "question_type" not in q:
            continue

        qtype = q.get("question_type")
        qid = (q.get("question_id") or "noid").strip()
        qname = (q.get("question_name") or qid).strip()
        qtext = q.get("question_content", "") or ""
        solution = (q.get("explanation") or {}).get("text", "") or ""
        qcat = _norm_category(q.get("question_category"))

        # ẢNH ĐỀ đặt SAU nội dung question_content
        qimg = q.get("question_image_url") or q.get("question_image")
        if qimg:
            qtext = f"{qtext}{_img_html(qimg, alt=qname)}"

        # BẢNG ĐỀ (nếu có) đặt SAU ảnh
        qtbls = q.get("question_table") or []
        if qtbls:
            qtext = f"{qtext}{_render_tables_block(qtbls)}"


        # ẢNH LỜI GIẢI đặt TRƯỚC nội dung solution
        eimg = (q.get("explanation") or {}).get("image_url") or (q.get("explanation") or {}).get("image")
        if eimg:
            solution = f"{_img_html(eimg, alt=f'explain-{qname}')}{(solution or '')}"

        # BẢNG LỜI GIẢI (nếu có) đặt SAU nội dung solution
        etbls = (q.get("explanation") or {}).get("table") or []
        if etbls:
            solution = f"{solution}{_render_tables_block(etbls)}"


        # Mỗi câu: chèn category riêng
        if qcat:
            quiz.add_category(qcat)

        if qtype == "multichoice":
            options = q.get("options", []) or []
            correct = set(q.get("correct_answer", []) or [])
            answers = []
            for idx, opt in enumerate(options):
                text = _get_opt_text(opt)

                # NEW: chèn ảnh option nếu có
                oimg = (opt or {}).get("option_image_url") or (opt or {}).get("option_image")
                if oimg:
                    text = f'{text}{_img_html(oimg, alt=f"opt-{idx+1}-{qname}")}'

                # NEW: chèn BẢNG option nếu có (option_table)
                otbl = (opt or {}).get("option_table")
                if otbl:
                    text = f'{text}{_render_table_html(otbl)}'

                grade = 100 if idx in correct else 0
                answers.append((text, grade))

            quiz.add_question(MultiChoiceQuestion(qname, qtext, answers, solution))
            count["multichoice"] += 1

        elif qtype == "kprime":
            options = q.get("options", []) or []
            correct = set(q.get("correct_answer", []) or [])
            pairs = []
            for idx, opt in enumerate(options):
                stmt = _get_opt_text(opt)

                # (Kprime T/F cho từng mệnh đề; nếu có ảnh kèm, vẫn gắn vào stmt)
                oimg = (opt or {}).get("option_image_url") or (opt or {}).get("option_image")
                if oimg:
                    stmt = f'{stmt}{_img_html(oimg, alt=f"opt-{idx+1}-{qname}")}'

                # NEW: bảng theo mệnh đề (nếu có)
                otbl = (opt or {}).get("option_table")
                if otbl:
                    stmt = f'{stmt}{_render_table_html(otbl)}'

                is_true = idx in correct
                pairs.append((stmt, is_true))

            quiz.add_question(ChoiceTFQuestion(qname, qtext, pairs, general_feedback_html=solution))
            count["kprime"] += 1

        elif qtype == "shortanswer":
            raw_answers = q.get("correct_answer", []) or []

            # Ưu tiên Key/Trả lời
            answers, cleaned_qtext = _extract_shortanswer_key_and_clean_text(qtext, solution)

            # Nếu JSON có correct_answer != rỗng thì dùng
            if not answers and raw_answers:
                blob = " ".join(a if isinstance(a, str) else str(a) for a in raw_answers)
                mnum = _re.search(r"([-+]?\d+(?:[.,]\d+)?)", blob)
                if mnum:
                    answers = _dedupe_variants(mnum.group(1))
                else:
                    answers = [str(raw_answers[0]).strip()]

            # Fallback: bắt số đầu tiên trong (qtext + solution)
            if not answers:
                blob = f"{qtext} {solution}"
                mnum = _re.search(r"([-+]?\d+(?:[.,]\d+)?)", blob)
                if mnum:
                    answers = _dedupe_variants(mnum.group(1))

            if not answers:
                answers = [""]  # vẫn cho import được

            quiz.add_question(ShortAnswerQuestion(qname, cleaned_qtext, answers, solution))
            count["shortanswer"] += 1

        else:
            # Fallback: multichoice
            options = q.get("options", []) or []
            correct = set(q.get("correct_answer", []) or [])
            answers = []
            for idx, opt in enumerate(options):
                text = _get_opt_text(opt)

                oimg = (opt or {}).get("option_image_url") or (opt or {}).get("option_image")
                if oimg:
                    text = f'{text}{_img_html(oimg, alt=f"opt-{idx+1}-{qname}")}'

                otbl = (opt or {}).get("option_table")
                if otbl:
                    text = f'{text}{_render_table_html(otbl)}'

                grade = 100 if idx in correct else 0
                answers.append((text, grade))

            quiz.add_question(MultiChoiceQuestion(qname, qtext, answers, solution))
            count["multichoice"] += 1

    Path(Path(xml_out).parent or ".").mkdir(parents=True, exist_ok=True)
    quiz.export(xml_out)
    print(
        f"✅ Xuất XML Moodle: {xml_out} | "
        f"MCQ: {count['multichoice']} | KPrime: {count['kprime']} | SA: {count['shortanswer']}"
    )
    return xml_out
