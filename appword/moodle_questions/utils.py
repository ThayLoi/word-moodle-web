# -*- coding: utf-8 -*-
from typing import List, Any, Optional

def xml_escape(s: Optional[str]) -> str:
    """Escape cơ bản cho các thẻ <text> không dùng CDATA."""
    s = s or ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

def render_quiz_xml(questions: List[Any]) -> str:
    """
    Ghép XML cuối cùng:
    - Chèn <question type="category"> MỖI KHI category thay đổi so với câu trước.
    - Mỗi phần tử trong `questions` phải có:
        - q.category_path: str (có thể rỗng; nếu rỗng sẽ KHÔNG chèn category)
        - q.to_xml(): -> str  (chỉ block <question type="...">...</question>, KHÔNG category)
    """
    out: List[str] = []
    out.append('<?xml version="1.0" ?>')
    out.append('<quiz>')

    last_category: Optional[str] = None

    for q in questions:
        cat = (getattr(q, "category_path", None) or "").strip()

        # Chèn category khi thay đổi
        if cat and cat != last_category:
            out.append('<question type="category">')
            out.append(f'  <category><text>{xml_escape(cat)}</text></category>')
            out.append('</question>')
            last_category = cat

        # Block câu hỏi
        out.append(q.to_xml())

    out.append('</quiz>')
    return "\n".join(out)
