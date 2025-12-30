# class MatchingQuestion
class MatchingQuestion:
    def __init__(self, name, text, answers, solution=""):
        self.name = name
        self.text = text
        self.qtype = "matching"
        self.answers = answers  # List of (subquestion, subanswer)
        self.solution = solution

    def to_xml(self):
        xml = f'<question type="{self.qtype}">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        for subq, suba in self.answers:
            xml += '  <subquestion format="html">\n'
            xml += f'    <text><![CDATA[{subq}]]></text>\n'
            xml += f'    <answer><text><![CDATA[{suba}]]></text></answer>\n'
            xml += '  </subquestion>\n'
        xml += '</question>\n'
        return xml
