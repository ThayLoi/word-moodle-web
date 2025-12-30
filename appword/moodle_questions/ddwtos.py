# moodle_questions/ddwtos.py

class DragDropWordsQuestion:
    def __init__(self, name, text, qtype="ddwtos", choices=None, solution=""):
        self.name = name
        self.text = text  # Ví dụ: "Trái [[1]] thường có màu [[2]]."
        self.qtype = qtype
        self.choices = choices or []  # danh sách các lựa chọn dạng (group, text)
        self.solution = solution

    def to_xml(self):
        xml = f'<question type="ddwtos">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += '  <defaultgrade>1.0</defaultgrade>\n'
        xml += '  <penalty>0.1</penalty>\n'
        xml += '  <hidden>0</hidden>\n'
        xml += '  <shuffleanswers>true</shuffleanswers>\n'
        xml += '  <correctfeedback><text>Đúng rồi!</text></correctfeedback>\n'
        xml += '  <partiallycorrectfeedback><text>Gần đúng!</text></partiallycorrectfeedback>\n'
        xml += '  <incorrectfeedback><text>Chưa chính xác.</text></incorrectfeedback>\n'

        for group, text in self.choices:
            xml += f'  <dragbox group="{group}">\n'
            xml += f'    <text><![CDATA[{text}]]></text>\n'
            xml += f'  </dragbox>\n'

        xml += '</question>\n'
        return xml
