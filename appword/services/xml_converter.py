import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

def format_text_with_image(text, image_url):
    """
    Tạo nội dung HTML: Text + Ảnh (nếu có URL)
    """
    content = text if text else ""
    # Nếu có URL ảnh online, chèn thẻ img html vào cuối
    if image_url:
        content += f'<p style="text-align:center"><img src="{image_url}" alt="image" class="img-responsive" /></p>'
    return content

def create_moodle_xml(questions_data, output_path):
    quiz = ET.Element("quiz")

    # Thêm category đầu file (nếu cần)
    # ... code category ...

    for q_data in questions_data:
        q_type = q_data.get("question_type", "multichoice")
        
        # Mapping loại câu hỏi sang chuẩn Moodle
        moodle_type = "multichoice"
        if q_type == "truefalse" or q_type == "kprime": # Kprime thường map sang TrueFalse hoặc Multichoice
            moodle_type = "truefalse" 
        elif q_type == "shortanswer":
            moodle_type = "shortanswer"
            
        question = ET.SubElement(quiz, "question", type=moodle_type)

        # 1. Tên câu hỏi
        name = ET.SubElement(question, "name")
        ET.SubElement(name, "text").text = q_data.get("question_name", "")

        # 2. Nội dung câu hỏi (KẾT HỢP TEXT VÀ URL ẢNH)
        questiontext = ET.SubElement(question, "questiontext", format="html")
        
        # --- LOGIC QUAN TRỌNG Ở ĐÂY ---
        final_content = format_text_with_image(
            q_data.get("question_content", ""), 
            q_data.get("question_image_url") # Lấy URL đã upload
        )
        # -----------------------------
        
        ET.SubElement(questiontext, "text").text = final_content

        # 3. Lời giải chung
        generalfeedback = ET.SubElement(question, "generalfeedback", format="html")
        expl_data = q_data.get("explanation", {})
        expl_text = expl_data.get("text", "")
        expl_img_url = expl_data.get("image_url")
        
        ET.SubElement(generalfeedback, "text").text = format_text_with_image(expl_text, expl_img_url)

        # 4. Các đáp án (Options)
        # ... (Logic tạo đáp án tương tự, nhớ check option_image_url) ...
        # Ví dụ cho shortanswer:
        if moodle_type == "shortanswer":
            for ans in q_data.get("correct_answer", []):
                answer = ET.SubElement(question, "answer", fraction="100", format="html")
                ET.SubElement(answer, "text").text = str(ans)

        # Ví dụ cho multichoice:
        elif moodle_type == "multichoice":
             # ... Logic loop options ...
             pass
    
    # Ghi ra file
    tree = ET.ElementTree(quiz)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)