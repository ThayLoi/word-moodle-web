# -*- coding: utf-8 -*-
import os
import io
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.document import Document as DocxDocument

# Thử import PIL để xử lý cắt ảnh
try:
    from PIL import Image
except ImportError:
    Image = None

def norm_path(p: str) -> str:
    return p.replace("\\", "/")

def table_to_json(table: Table):
    rows = [[c.text.strip() for c in r.cells] for r in table.rows]
    return {"headers": (rows[0] if rows else []), "rows": (rows[1:] if rows else [])}

def iter_block_items(parent):
    from docx.oxml.ns import qn
    elm = parent.element.body if isinstance(parent, DocxDocument) else parent._element
    for child in elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)

def _crop_image_from_xml(pil_img, blip_element):
    """
    Hàm nội bộ: Cắt ảnh dựa trên thẻ a:srcRect trong XML của Word.
    Word lưu ảnh gốc và chỉ dùng lệnh XML để che bớt phần thừa.
    Hàm này sẽ cắt bỏ phần thừa đó thật sự.
    """
    if pil_img is None:
        return None
        
    try:
        # blip_element là thẻ <a:blip>, cha của nó là <pic:blipFill>
        blip_fill = blip_element.getparent()
        if blip_fill is None:
            return pil_img

        # Namespace của DrawingML
        ns = {
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'
        }

        # Tìm thẻ srcRect (Source Rectangle) chứa thông số crop
        src_rect = blip_fill.find('a:srcRect', ns)
        if src_rect is None:
            return pil_img # Không có lệnh crop

        # Lấy thông số (đơn vị 1/1000 của phần trăm)
        l = int(src_rect.get('l') or 0)
        t = int(src_rect.get('t') or 0)
        r = int(src_rect.get('r') or 0)
        b = int(src_rect.get('b') or 0)

        if l == 0 and t == 0 and r == 0 and b == 0:
            return pil_img # Không crop

        width, height = pil_img.size

        # Tính toán pixel cần cắt
        # 100000 đơn vị = 100%
        left = (l / 100000.0) * width
        top = (t / 100000.0) * height
        right = width - ((r / 100000.0) * width)
        bottom = height - ((b / 100000.0) * height)

        # Thực hiện cắt
        return pil_img.crop((left, top, right, bottom))
    except Exception as e:
        print(f"[Warn] Lỗi khi crop ảnh: {e}")
        return pil_img

def save_inline_images(para, image_dir, qid, part="content", idx=0):
    paths = []
    # Duyệt qua các Run trong đoạn văn
    for run_idx, run in enumerate(para.runs):
        # Kiểm tra xem run có chứa drawing (hình ảnh) không
        # Dùng xpath để tìm thẻ blip (bitmap) bên trong drawing
        inline_shapes = run.element.xpath('.//pic:blipFill/a:blip')
        
        for img_idx, blip in enumerate(inline_shapes):
            # Lấy ID liên kết (rId)
            rId = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if not rId:
                continue
            
            # Lấy part hình ảnh từ document
            image_part = para.part.related_parts.get(rId)
            if not image_part:
                continue

            # Xác định đuôi file
            ext = image_part.content_type.split("/")[-1]
            if ext.lower() not in {"png", "jpeg", "jpg", "gif", "bmp", "webp"}:
                ext = "png"
            
            img_filename = f"{qid}_{part}_{idx}_{run_idx}_{img_idx}.{ext}"
            img_path = os.path.join(image_dir, img_filename)
            
            # --- XỬ LÝ LƯU ẢNH ---
            if Image:
                try:
                    # 1. Mở ảnh từ dữ liệu nhị phân (blob)
                    pil_img = Image.open(io.BytesIO(image_part.blob))
                    
                    # 2. Thực hiện Crop (nếu Word có lệnh crop)
                    pil_img = _crop_image_from_xml(pil_img, blip)
                    
                    # 3. Lưu xuống đĩa
                    pil_img.save(img_path)
                except Exception as e:
                    print(f"Lỗi xử lý ảnh {img_filename} bằng PIL: {e}, dùng chế độ lưu thô.")
                    # Fallback: Nếu lỗi PIL thì lưu thô như cũ
                    with open(img_path, "wb") as f:
                        f.write(image_part.blob)
            else:
                # Nếu không cài Pillow thì lưu thô
                with open(img_path, "wb") as f:
                    f.write(image_part.blob)

            paths.append(norm_path(img_path))
            
    return paths or None