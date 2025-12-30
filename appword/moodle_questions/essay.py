# class EssayQuestion
class EssayQuestion:
    def __init__(self, name, text, solution=""):
        self.name = name
        self.text = text
        self.qtype = "essay"
        self.solution = solution

    def to_xml(self):
        xml = f'<question type="essay">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += '  <responseformat>editor</responseformat>\n'
        xml += '  <responserequired>1</responserequired>\n'
        xml += '  <responsefieldlines>10</responsefieldlines>\n'
        xml += '  <attachments>0</attachments>\n'
        xml += f'  <graderinfo format="html"><text><![CDATA[{self.solution}]]></text></graderinfo>\n'
        xml += '  <responsetemplate format="html"><text><![CDATA[]]></text></responsetemplate>\n'
        xml += '</question>\n'
        return xml
