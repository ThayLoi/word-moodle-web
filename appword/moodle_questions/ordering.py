# moodle_questions/ordering.py

class OrderingQuestion:
    def __init__(self, name, text, answers, solution="", extra=None):
        self.name = name
        self.text = text
        self.qtype = "ordering"
        self.answers = answers  # Danh sách các mục theo thứ tự đúng
        self.solution = solution
        self.extra = extra or {}

    def to_xml(self):
        xml = f'''  <question type="ordering">
    <name><text>{self.name}</text></name>
    <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>
    <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>
    <defaultgrade>1</defaultgrade>
    <penalty>0.3333333</penalty>
    <hidden>0</hidden>
    <layouttype>VERTICAL</layouttype>
    <selecttype>ALL</selecttype>
    <selectcount>0</selectcount>
    <gradingtype>ABSOLUTE_POSITION</gradingtype>
    <showgrading>SHOW</showgrading>
    <numberingstyle>none</numberingstyle>
    <correctfeedback format="html"><text>Chính xác!</text></correctfeedback>
    <partiallycorrectfeedback format="html"><text>Gần đúng, hãy thử lại.</text></partiallycorrectfeedback>
    <incorrectfeedback format="html"><text>Chưa chính xác.</text></incorrectfeedback>
    <shownumcorrect>1</shownumcorrect>
'''
        for i, ans in enumerate(self.answers, 1):
            xml += f'    <answer fraction="{i}" format="moodle_auto_format"><text>{ans}</text></answer>\n'

        xml += "  </question>\n"
        return xml
