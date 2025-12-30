# moodle_questions/gapselect.py

class GapSelectQuestion:
    def __init__(self, name, text, qtype="gapselect", choices=None, solution="", extra=None):
        self.name = name
        self.text = text  # Ví dụ: "Trái [[1]] thường có màu [[2]]."
        self.qtype = qtype
        self.choices = choices or []
        self.solution = solution
        self.extra = extra or {}

    def to_xml(self):
        xml = f'''  <question type="gapselect">
    <name><text>{self.name}</text></name>
    <questiontext format="html">
      <text><![CDATA[<p>{self.text}</p>]]></text>
    </questiontext>
    <generalfeedback format="html">
      <text><![CDATA[<p>{self.solution}</p>]]></text>
    </generalfeedback>
    <defaultgrade>1</defaultgrade>
    <penalty>0</penalty>
    <hidden>0</hidden>
    <shuffleanswers>1</shuffleanswers>
    <correctfeedback format="html"><text></text></correctfeedback>
    <partiallycorrectfeedback format="html"><text></text></partiallycorrectfeedback>
    <incorrectfeedback format="html"><text></text></incorrectfeedback>
'''
        for group_index, options in enumerate(self.choices, 1):
            for opt in options:
                xml += f'''    <selectoption>
      <text>{opt}</text>
      <group>{group_index}</group>
    </selectoption>
'''
        xml += '  </question>\n'
        return xml
