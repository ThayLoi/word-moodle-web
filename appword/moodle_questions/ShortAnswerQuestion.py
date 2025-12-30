# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from .utils import xml_escape

class ShortAnswerQuestion:
    """
    SHORTANSWER
    - KHÔNG chèn category bên trong to_xml().
    - answers: List[Dict[str, Any]] với keys:
        - text: str (đáp án)
        - fraction: int|float (0..100)
        - feedback_html: str (optional)
    """
    def __init__(
        self,
        name: str,
        questiontext_html: str,
        answers: List[Dict[str, Any]],
        generalfeedback_html: str = "",
        defaultgrade: float = 1.0,
        penalty: float = 0.1,
        hidden: int = 0,
        usecase: int = 0,
        category_path: Optional[str] = None,
    ):
        self.name = name
        self.questiontext_html = questiontext_html or ""
        self.answers = answers or []
        self.generalfeedback_html = generalfeedback_html or ""
        self.defaultgrade = float(defaultgrade)
        self.penalty = float(penalty)
        self.hidden = int(hidden)
        self.usecase = int(usecase)  # 0 = not case sensitive, 1 = case sensitive
        self.category_path = category_path  # để builder sử dụng

    def to_xml(self) -> str:
        # KHÔNG render category ở đây
        lines = []
        lines.append('<question type="shortanswer">')
        lines.append(f'  <name><text>{xml_escape(self.name)}</text></name>')
        lines.append('  <questiontext format="html">')
        lines.append(f'    <text><![CDATA[{self.questiontext_html}]]></text>')
        lines.append('  </questiontext>')
        lines.append('  <generalfeedback format="html">')
        lines.append(f'    <text><![CDATA[{self.generalfeedback_html}]]></text>')
        lines.append('  </generalfeedback>')
        lines.append(f'  <defaultgrade>{self.defaultgrade:g}</defaultgrade>')
        lines.append(f'  <penalty>{self.penalty}</penalty>')
        lines.append(f'  <hidden>{self.hidden}</hidden>')
        lines.append(f'  <usecase>{self.usecase}</usecase>')

        for ans in self.answers:
            if isinstance(ans, dict):
                fraction = float(ans.get("fraction", 0))
                text_val = ans.get("text", "") or ans.get("answer", "") or ""
                feedback_html = ans.get("feedback_html", "")
            elif isinstance(ans, (tuple, list)):
                text_val = str(ans[0]) if len(ans) >= 1 else ""
                frac = float(ans[1]) if len(ans) >= 2 else 100.0
                fraction = int(frac*100) if 0.0 <= frac <= 1.0 else int(frac)
                feedback_html = str(ans[2]) if len(ans) >= 3 else ""
            else:
                text_val = str(ans)
                fraction = 100
                feedback_html = ""
            lines.append(f'  <answer fraction="{int(fraction)}">')
            lines.append(f'    <text><![CDATA[{text_val}]]></text>')
            if feedback_html:
                lines.append('    <feedback format="html">')
                lines.append(f'      <text><![CDATA[{feedback_html}]]></text>')
                lines.append('    </feedback>')
            lines.append('  </answer>')

        lines.append('</question>')
        return "\n".join(lines)
