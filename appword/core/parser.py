# -*- coding: utf-8 -*-
import os
import re
import json
from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from appword.core.utils import save_inline_images, table_to_json, iter_block_items

# --- Helpers bắt Key / Trả lời cho shortanswer ---
_KEY_RE = re.compile(
    r"<\s*Key\s*=\s*([-+]?\d+(?:[.,]\d+)?)\s*>",
    flags=re.IGNORECASE
)
_TRALOI_RE = re.compile(
    r"(?:Tr(?:ả|a)\s*l(?:ờ|o)i|Đáp\s*án|Đáp\s*số|Kết\s*quả)\s*[:：]\s*([-+]?\d+(?:[.,]\d+)?)",
    flags=re.IGNORECASE,
)

def _dedupe_num_variants(num_str: str):
    """
    Trả các biến thể số chấp nhận:
    - Số nguyên: 1 biến thể (bỏ + nếu có).
    - Số thập phân: trả cả dạng dùng '.' và ',' (không lặp).
    """
    s = (num_str or "").strip()
    if not s:
        return []
    if re.fullmatch(r"[-+]?\d+", s):  # số nguyên
        return [s.lstrip("+")]
    dot = s.replace(",", ".").lstrip("+")
    comma = s.replace(".", ",").lstrip("+")
    out = []
    for v in (dot, comma):
        if v not in out:
            out.append(v)
    return out

def extract_key_and_clean(content_text: str, explanation_text: str):
    """
    Ưu tiên bắt <Key=...> trong nội dung câu hỏi, xóa tag đó khỏi content.
    Nếu không có, thử 'Trả lời: ...' (hoặc 'Đáp án/Đáp số/Kết quả: ...') trong lời giải.
    Trả về: (answers:list[str], cleaned_content:str)
    """
    answers = []
    cleaned = content_text or ""

    # 1) Tìm trong content: <Key=...>
    mk = _KEY_RE.search(cleaned)
    if mk:
        answers = _dedupe_num_variants(mk.group(1))
        cleaned = _KEY_RE.sub("", cleaned).strip()

    # 2) Nếu chưa có, tìm trong lời giải
    if not answers and (explanation_text or "").strip():
        mt = _TRALOI_RE.search(explanation_text)
        if mt:
            answers = _dedupe_num_variants(mt.group(1))

    return answers, cleaned


def parse_docx_to_json(
    docx_path,
    output_dir="output_questions",
    image_dir="images",
    author="GV Huỳnh Văn Lợi"
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    image_dir_full = Path(output_dir) / image_dir
    image_dir_full.mkdir(parents=True, exist_ok=True)

    doc = Document(docx_path)

    questions = []
    current_q = None
    options = []
    correct_answers = []
    is_in_explanation = False
    current_tags = []
    title_candidate = ""
    q_counter = 0
    has_lower_option = False

    re_question_head = re.compile(r"^Câu\s+(\d+)\s*[\.\:\-]?\s*(.*)$", flags=re.IGNORECASE)
    re_id_tag = re.compile(r"^\[([^\]]+)\]\s*(.*)", flags=re.IGNORECASE)
    re_option = re.compile(r"^([A-Da-d])[\.\)]\s*(.+)")

    # Cho phép "Lời giải" có/không dấu ":" sau đó
    def _is_loi_giai(line: str) -> bool:
        s = (line or "").strip().lower()
        return s.startswith("lời giải") or s.startswith("loi giai")

    def flush_current():
        nonlocal current_q, options, correct_answers, questions, has_lower_option
        if current_q:
            q_number = len([q for q in questions if 'question_type' in q]) + 1
            questions.append({"//": f"===== Câu {q_number} ====="})

            # ✳️ Bắt Key/Trả lời và làm sạch content trước khi xác định loại câu hỏi
            ans_from_key, cleaned_content = extract_key_and_clean(
                current_q.get("question_content", ""),
                current_q.get("explanation", {}).get("text", ""),
            )
            current_q["question_content"] = cleaned_content

            if not options:
                # Không có phương án -> shortanswer
                current_q["question_type"] = "shortanswer"

                if ans_from_key:
                    # Ưu tiên Key/Trả lời
                    current_q["correct_answer"] = ans_from_key
                else:
                    # Fallback: xem trong 'Lời giải' có 'Đáp án/Đáp số/Kết quả:'
                    ans_match = re.search(
                        r"(Đáp án|Đáp số|Kết quả)\s*[:：]\s*(.+)",
                        current_q["explanation"]["text"]
                    )
                    if ans_match:
                        ans_line = ans_match.group(2).strip().splitlines()[0].strip()
                        current_q["correct_answer"] = [ans_line]
                    else:
                        # vẫn không có -> cố gắng lấy từ correct_answers đang gom (nếu có)
                        current_q["correct_answer"] = ans_from_key or (correct_answers if correct_answers else [])
            else:
                # Có phương án -> MCQ/KPRIME
                if current_q.get("question_type") not in ("multichoice", "kprime"):
                    current_q["question_type"] = "kprime" if has_lower_option else "multichoice"
                else:
                    if has_lower_option:
                        current_q["question_type"] = "kprime"

                current_q["options"] = [{
                    "option_text": opt.get("text"),
                    "option_image": opt.get("image"),
                    "option_table": opt.get("table")
                } for opt in sorted(options, key=lambda o: o["letter"])]

                current_q["correct_answer"] = correct_answers if correct_answers else []

            current_q["metadata"]["source"] = {
                "file_name": Path(docx_path).name,
                "full_path": str(Path(docx_path).resolve()),
                "question_index": q_number
            }
            questions.append(current_q)

        current_q = None
        options = []
        correct_answers = []
        has_lower_option = False

    for b_idx, block in enumerate(iter_block_items(doc)):
        if isinstance(block, Paragraph):
            text = (block.text or "").strip()
            if not text and not block.runs:
                continue

            style_name = (block.style.name or "").lower()
            if style_name.startswith("heading"):
                current_tags = [text]
                title_candidate = text
                continue

            m_q = re_question_head.match(text)
            if m_q:
                flush_current()
                tail = (m_q.group(2) or "").strip()

                m_id = re_id_tag.match(tail)
                if m_id:
                    qid = m_id.group(1).strip()
                    q_content = m_id.group(2).strip()
                else:
                    q_counter += 1
                    qid = f"Q{str(q_counter).zfill(3)}"
                    q_content = tail

                current_q = {
                    "question_type": "multichoice",
                    "question_id": qid,
                    "question_name": title_candidate or "",
                    "question_category": title_candidate or "",
                    "question_content": q_content,
                    "question_image": None,
                    "question_table": [],
                    "options": [],
                    "correct_answer": None,
                    "explanation": {"text": "", "image": None, "table": []},
                    "metadata": {"difficulty": "medium", "tags": current_tags, "author": author, "source": {}}
                }
                is_in_explanation = False
                continue

            if current_q and not is_in_explanation and _is_loi_giai(text):
                is_in_explanation = True
                # Cắt phần "Lời giải" (nếu có dấu ":" thì bỏ luôn)
                after = text[len("Lời giải"):].lstrip(" :：").strip() if text.lower().startswith("lời giải") else text[len("loi giai"):].lstrip(" :：").strip()
                current_q["explanation"]["text"] = after
                img_paths = save_inline_images(block, str(image_dir_full), current_q["question_id"], part="explanation", idx=b_idx)
                if img_paths:
                    current_q["explanation"]["image"] = img_paths[0]
                continue

            if current_q and not is_in_explanation:
                m_opt = re_option.match(text)
                if m_opt:
                    opt_letter_raw = m_opt.group(1)
                    opt_text = m_opt.group(2).strip()
                    if opt_letter_raw.islower():
                        has_lower_option = True
                    opt_letter = opt_letter_raw.upper()

                    # Chữ gạch dưới => đáp án đúng (với MCQ)
                    is_underlined = any(run.font.underline for run in block.runs if (run.text or "").strip())
                    if is_underlined and "ABCD".find(opt_letter) != -1:
                        correct_answers.append("ABCD".index(opt_letter))

                    img_paths = save_inline_images(block, str(image_dir_full), current_q["question_id"], part=f"opt{opt_letter}", idx=b_idx)
                    options.append({
                        "letter": opt_letter,
                        "text": opt_text,
                        "image": (img_paths[0] if img_paths else None),
                        "table": None
                    })
                    continue

            if current_q:
                if is_in_explanation:
                    if text:
                        current_q["explanation"]["text"] += (("\n" if current_q["explanation"]["text"] else "") + text)
                    img_paths = save_inline_images(block, str(image_dir_full), current_q["question_id"], part="explanation", idx=b_idx)
                    if img_paths and not current_q["explanation"]["image"]:
                        current_q["explanation"]["image"] = img_paths[0]
                else:
                    if text:
                        if not current_q["question_content"]:
                            current_q["question_content"] = text
                        else:
                            current_q["question_content"] += "\n" + text
                    img_paths = save_inline_images(block, str(image_dir_full), current_q["question_id"], part="content", idx=b_idx)
                    if img_paths and not current_q["question_image"]:
                        current_q["question_image"] = img_paths[0]

        elif isinstance(block, Table) and current_q:
            tbl_json = table_to_json(block)
            if is_in_explanation:
                current_q["explanation"]["table"].append(tbl_json)
            else:
                current_q["question_table"].append(tbl_json)

    # flush cuối
    flush_current()

    out_file = os.path.join(output_dir, "questionsTF.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã parse {len([q for q in questions if 'question_type' in q])} câu hỏi → {out_file}")
    return out_file
