# class CalculatedMultiQuestion
class CalculatedMultiQuestion:
    def __init__(self, name, text, answers, solution="", vars_def=None):
        self.name = name
        self.text = text
        self.qtype = "calculatedmulti"
        self.answers = answers  # List of (expression, fraction, feedback)
        self.solution = solution
        self.vars_def = vars_def or {}

    def to_xml(self):
        xml = f'<question type="{self.qtype}">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += '  <defaultgrade>1.0</defaultgrade>\n'
        xml += '  <penalty>0.1</penalty>\n'
        xml += '  <hidden>0</hidden>\n'
        xml += '  <single>true</single>\n'
        xml += '  <shuffleanswers>true</shuffleanswers>\n'
        xml += '  <answernumbering>abc</answernumbering>\n'
        for text, fraction, feedback in self.answers:
            xml += f'  <answer fraction="{fraction}" format="moodle_auto_format">\n'
            xml += f'    <text>{text}</text>\n'
            xml += f'    <feedback><text>{feedback}</text></feedback>\n'
            xml += f'  </answer>\n'
        xml += '</question>\n'
        return xml

