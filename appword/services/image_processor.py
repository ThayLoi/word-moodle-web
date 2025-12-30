from appword.services.uploader import upload_image_to_host

def process_images_in_data(data_list):
    """
    Duyệt qua danh sách câu hỏi, upload ảnh và cập nhật URL.
    """
    print("--- BẮT ĐẦU UPLOAD ẢNH ---")
    count = 0
    
    for question in data_list:
        # 1. Xử lý ảnh chính của câu hỏi
        if question.get("question_image") and not question.get("question_image_url"):
            url = upload_image_to_host(question["question_image"])
            if url:
                question["question_image_url"] = url
                count += 1

        # 2. Xử lý ảnh trong lời giải (explanation)
        expl = question.get("explanation", {})
        if expl and expl.get("image") and not expl.get("image_url"):
            url = upload_image_to_host(expl["image"])
            if url:
                expl["image_url"] = url
                question["explanation"]["image_url"] = url # Cập nhật lại
                count += 1

        # 3. Xử lý ảnh trong các đáp án (options)
        if "options" in question:
            for opt in question["options"]:
                if opt.get("option_image") and not opt.get("option_image_url"):
                    url = upload_image_to_host(opt["option_image"])
                    if url:
                        opt["option_image_url"] = url
                        count += 1
                        
    print(f"--- ĐÃ UPLOAD {count} ẢNH ---")
    return data_list