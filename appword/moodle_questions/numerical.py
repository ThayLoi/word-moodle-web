# moodle_questions/numerical.py

class NumericalQuestion:
    def __init__(self, name, text, answers, solution=""):
        self.name = name
        self.text = text
        self.answers = answers  # List of tuples: (answer, tolerance, fraction, feedback)
        self.solution = solution

    def to_xml(self):
        xml = f'<question type="numerical">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += f'  <defaultgrade>1.0</defaultgrade>\n'
        xml += f'  <penalty>0.1</penalty>\n'
        xml += f'  <hidden>0</hidden>\n'

        for ans, tol, frac, fb in self.answers:
            xml += f'  <answer fraction="{frac}" tolerance="{tol}">\n'
            xml += f'    <text>{ans}</text>\n'
            xml += f'    <feedback><text><![CDATA[{fb}]]></text></feedback>\n'
            xml += f'  </answer>\n'

        xml += '</question>\n'
        return xml
