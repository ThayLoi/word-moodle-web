class ClozeQuestion:
    def __init__(self, name, text, solution=""):
        self.name = name
        self.text = text
        self.qtype = "cloze"
        self.solution = solution

    def to_xml(self):
        xml = f'<question type="{self.qtype}">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += '  <defaultgrade>1.0</defaultgrade>\n'
        xml += '  <penalty>0.1</penalty>\n'
        xml += '  <hidden>0</hidden>\n'
        xml += '</question>\n'
        return xml
