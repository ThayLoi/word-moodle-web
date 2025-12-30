# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Tuple, Optional
from appword.moodle_questions.utils import xml_escape

class ChoiceTFQuestion:
    """
    K-prime (4 mệnh đề, 2 cột True/False). pairs: List[(text_html, is_true)]
    """
    def __init__(
        self,
        name: str,
        text_html: str,
        pairs: List[Tuple[str, bool]],
        general_feedback_html: str = "",
        category: Optional[str] = None,
        scoringmethod: str = "kprime",
        shuffleanswers: bool = True,
        hidden: int = 0
    ) -> None:
        self.name = name
        self.text_html = text_html
        self.pairs = pairs
        self.general_feedback_html = general_feedback_html
        self.category = category
        self.scoringmethod = scoringmethod
        self.shuffleanswers = shuffleanswers
        self.hidden = hidden

    def to_xml(self) -> str:
        rows = len(self.pairs)
        out: List[str] = []
        out.append('<question type="kprime">')
        out.append(f'  <name><text>{xml_escape(self.name)}</text></name>')
        out.append('  <questiontext format="html">')
        out.append(f'    <text><![CDATA[{self.text_html}]]></text>')
        out.append('  </questiontext>')
        if self.general_feedback_html:
            out.append('  <generalfeedback format="html">')
            out.append(f'    <text><![CDATA[{self.general_feedback_html}]]></text>')
            out.append('  </generalfeedback>')
        out.append('  <defaultgrade>1</defaultgrade>')
        out.append('  <penalty>0.3333333</penalty>')
        out.append(f'  <hidden>{self.hidden}</hidden>')
        out.append(f'  <scoringmethod>{xml_escape(self.scoringmethod)}</scoringmethod>')
        out.append(f'  <shuffleanswers>{"true" if self.shuffleanswers else "false"}</shuffleanswers>')
        out.append(f'  <numberofrows>{rows}</numberofrows>')
        out.append('  <numberofcolumns>2</numberofcolumns>')
        # Rows
        for i, (stmt_html, _) in enumerate(self.pairs, start=1):
            out.append(f'  <row number="{i}">')
            out.append('    <optiontext format="html">')
            out.append(f'      <text><![CDATA[{stmt_html}]]></text>')
            out.append('    </optiontext>')
            out.append('    <feedbacktext format="html"><text></text></feedbacktext>')
            out.append('  </row>')
        # Columns
        out.append('  <column number="1">')
        out.append('    <responsetext>True</responsetext>')
        out.append('  </column>')
        out.append('  <column number="2">')
        out.append('    <responsetext>False</responsetext>')
        out.append('  </column>')
        # Weights
        for i, (_, is_true) in enumerate(self.pairs, start=1):
            if is_true:
                out.append(f'  <weight rownumber="{i}" columnnumber="1"><value>1.000</value></weight>')
                out.append(f'  <weight rownumber="{i}" columnnumber="2"><value>0.000</value></weight>')
            else:
                out.append(f'  <weight rownumber="{i}" columnnumber="1"><value>0.000</value></weight>')
                out.append(f'  <weight rownumber="{i}" columnnumber="2"><value>1.000</value></weight>')
        out.append('</question>')
        return "\n".join(out)
