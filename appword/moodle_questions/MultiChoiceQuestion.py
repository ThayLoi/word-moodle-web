# -*- coding: utf-8 -*-
from typing import List, Optional, Dict, Any
from .utils import xml_escape

class MultiChoiceQuestion:
    """
    MULTICHOICE
    - KHÔNG chèn category bên trong to_xml().
    - answers: List[Dict[str, Any]] với keys:
        - text: str (HTML)
        - fraction: int|float (0..100)
        - feedback_html: str (optional)
    """
    def __init__(
        self,
        name: str,
        questiontext_html: str,
        answers: List[Dict[str, Any]],
        generalfeedback_html: str = "",
        shuffleanswers: bool = True,
        single: bool = True,
        answernumbering: str = "ABCD",
        defaultgrade: float = 1.0,
        penalty: float = 0.3333333,
        hidden: int = 0,
        category_path: Optional[str] = None,
    ):
        self.name = name
        self.questiontext_html = questiontext_html or ""
        self.answers = answers or []
        self.generalfeedback_html = generalfeedback_html or ""
        self.shuffleanswers = bool(shuffleanswers)
        self.single = bool(single)
        self.answernumbering = answernumbering or "ABCD"
        self.defaultgrade = float(defaultgrade)
        self.penalty = float(penalty)
        self.hidden = int(hidden)
        self.category_path = category_path  # để builder sử dụng

    def to_xml(self) -> str:
        # KHÔNG render category ở đây
        lines = []
        lines.append('<question type="multichoice">')
        lines.append(f'  <name><text>{xml_escape(self.name)}</text></name>')
        lines.append('  <questiontext format="html">')
        lines.append(f'    <text><![CDATA[{self.questiontext_html}]]></text>')
        lines.append('  </questiontext>')
        lines.append('  <generalfeedback format="html">')
        lines.append(f'    <text><![CDATA[{self.generalfeedback_html}]]></text>')
        lines.append('  </generalfeedback>')
        lines.append(f'  <shuffleanswers>{"true" if self.shuffleanswers else "false"}</shuffleanswers>')
        lines.append(f'  <single>{"true" if self.single else "false"}</single>')
        lines.append(f'  <answernumbering>{xml_escape(self.answernumbering)}</answernumbering>')
        lines.append(f'  <defaultgrade>{self.defaultgrade:g}</defaultgrade>')
        lines.append(f'  <penalty>{self.penalty}</penalty>')
        lines.append(f'  <hidden>{self.hidden}</hidden>')

        for ans in self.answers:
            # hỗ trợ nhiều dạng: dict | tuple/list | str
            if isinstance(ans, dict):
                fraction = float(ans.get("fraction", 0))
                text_html = ans.get("text", "") or ans.get("answer", "") or ""
                feedback_html = ans.get("feedback_html", "")
            elif isinstance(ans, (tuple, list)):
                text_html = str(ans[0]) if len(ans) >= 1 else ""
                frac = float(ans[1]) if len(ans) >= 2 else 0.0
                # nếu 0..1 coi là tỉ lệ
                fraction = int(frac*100) if 0.0 <= frac <= 1.0 else int(frac)
                feedback_html = str(ans[2]) if len(ans) >= 3 else ""
            else:
                text_html = str(ans)
                fraction = 0
                feedback_html = ""
            lines.append(f'  <answer fraction="{int(fraction)}">')
            lines.append(f'    <text><![CDATA[{text_html}]]></text>')
            if feedback_html:
                lines.append('    <feedback format="html">')
                lines.append(f'      <text><![CDATA[{feedback_html}]]></text>')
                lines.append('    </feedback>')
            lines.append('  </answer>')

        lines.append('</question>')
        return "\n".join(lines)
