# moodle_questions/ddmarker.py

class DragDropMarkerQuestion:    
    def __init__(self, name, text, image, markers=None, bgwidth=600, bgheight=400, solution="", qtype=None):
        self.name = name
        self.text = text
        self.qtype = "ddmarker"  # luôn cố định loại câu hỏi
        self.image = image
        self.markers = markers or []
        self.bgwidth = bgwidth
        self.bgheight = bgheight
        self.solution = solution


    def to_xml(self):
        xml = f'<question type="ddmarker">\n'
        xml += f'  <name><text>{self.name}</text></name>\n'
        xml += f'  <questiontext format="html"><text><![CDATA[{self.text}<br><img src="@@PLUGINFILE@@/{self.image}" width="{self.bgwidth}" height="{self.bgheight}" />]]></text></questiontext>\n'
        xml += f'  <generalfeedback format="html"><text><![CDATA[{self.solution}]]></text></generalfeedback>\n'
        xml += f'  <defaultgrade>1.0</defaultgrade>\n'
        xml += f'  <penalty>0.1</penalty>\n'
        xml += f'  <hidden>0</hidden>\n'

        xml += '  <drag>\n'
        for i, (label, _, _) in enumerate(self.markers, 1):
            xml += f'    <dragitem>\n'
            xml += f'      <text>{label}</text>\n'
            xml += f'      <noofdrags>1</noofdrags>\n'
            xml += f'      <infinite>false</infinite>\n'
            xml += f'    </dragitem>\n'
        xml += '  </drag>\n'

        xml += '  <drop>\n'
        for i, (label, x, y) in enumerate(self.markers, 1):
            xml += f'    <dropzone>\n'
            xml += f'      <xleft>{x}</xleft>\n'
            xml += f'      <ytop>{y}</ytop>\n'
            xml += f'      <choice>{i}</choice>\n'
            xml += f'    </dropzone>\n'
        xml += '  </drop>\n'

        # Nếu cần thêm ảnh thật, thay thế chỗ này bằng ảnh base64 đã mã hóa
        xml += f'  <file name="{self.image}" path="/" encoding="base64">PLACEHOLDER_IMAGE_BASE64</file>\n'
        xml += '</question>\n'
        return xml
