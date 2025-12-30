# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Tuple, Union


class MoodleQuiz:
    """
    Hỗ trợ 2 flow:
    1) Cũ: set_categories(...) -> add_question(...). Category sẽ ghi MỘT LẦN ở đầu file.
    2) Mới (khuyên dùng): add_category(path) ngay trước add_question(...).
       Category sẽ được chèn ngay trước câu hỏi tương ứng (interleaved).
    """

    def __init__(self):
        # Flow cũ
        self._categories: List[str] = []
        self._questions: List[object] = []

        # Flow mới (interleaved)
        # item = ("category", "path") | ("question", q_obj)
        self._items: List[Tuple[str, Union[str, object]]] = []
        self._last_category: str | None = None  # tránh lặp category liền kề

    # --- Category API ---
    def set_categories(self, categories: List[str]) -> None:
        """Flow cũ: ghi đè danh sách category (đã được lọc, dedupe, sắp thứ tự)."""
        self._categories = list(categories or [])

    def add_category(self, cat: str) -> None:
        """
        Flow mới: chèn một <question type="category"> vào đúng vị trí hiện tại
        (tức là ngay trước câu hỏi tiếp theo).
        - Bỏ qua cat rỗng/"0"
        - Tránh lặp nếu trùng hệt với category vừa chèn trước đó
        """
        if not cat:
            return
        cat = str(cat).strip().strip("/")
        if not cat or cat == "0":
            return
        if self._last_category == cat:
            return
        self._items.append(("category", cat))
        self._last_category = cat

        # vẫn giữ tương thích ngược nếu ai đó đọc self._categories
        if cat not in self._categories:
            self._categories.append(cat)

    # --- Question API ---
    def add_question(self, q_obj: object) -> None:
        """q_obj phải có .to_xml() -> str"""
        # Lưu cho flow cũ (tương thích ngược)
        self._questions.append(q_obj)
        # Lưu cho flow mới (interleaved)
        self._items.append(("question", q_obj))

    # --- XML helpers (flow cũ) ---
    def _categories_to_xml(self) -> str:
        lines = []
        for cat in self._categories:
            lines.append(
                '<question type="category">\n'
                f'  <category><text>{cat}</text></category>\n'
                '</question>'
            )
        return "\n".join(lines)

    def _questions_to_xml(self) -> str:
        return "\n".join(q.to_xml() for q in self._questions)

    # --- XML helpers (flow mới) ---
    def _items_to_xml(self) -> str:
        parts: List[str] = []
        for kind, payload in self._items:
            if kind == "category":
                parts.append(
                    '<question type="category">\n'
                    f'  <category><text>{payload}</text></category>\n'
                    '</question>'
                )
            elif kind == "question":
                parts.append(payload.to_xml())
        return "\n".join(parts)

    def to_xml(self) -> str:
        parts = ['<?xml version="1.0" ?>', '<quiz>']

        if self._items:
            # Flow mới: xuất theo thứ tự interleaved đã ghi
            parts.append(self._items_to_xml())
        else:
            # Flow cũ: category một lần ở đầu, sau đó tất cả câu hỏi
            if self._categories:
                parts.append(self._categories_to_xml())
            if self._questions:
                parts.append(self._questions_to_xml())

        parts.append('</quiz>')
        return "\n".join(parts)

    def export(self, filepath: str) -> None:
        xml = self.to_xml()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(xml)
