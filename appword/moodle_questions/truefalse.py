# class TrueFalseQuestion
class TrueFalseQuestion:
    def __init__(self, name, text, correct=True, solution=""):
        self.name = name
        self.text = text
        self.correct = correct
        self.solution = solution

    def to_xml(self):
        xml = '<question type="truefalse">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'

        if self.correct:
            xml += '  <answer fraction="100"><text>true</text></answer>\n'
            xml += '  <answer fraction="0"><text>false</text></answer>\n'
        else:
            xml += '  <answer fraction="0"><text>true</text></answer>\n'
            xml += '  <answer fraction="100"><text>false</text></answer>\n'

        xml += '</question>\n'
        return xml
