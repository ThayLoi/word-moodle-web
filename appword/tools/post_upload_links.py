# -*- coding: utf-8 -*-
from typing import Any, Dict
from appword.services.uploader import ImageUploader

def _is_str(s): 
    return isinstance(s, str) and s.strip()

def _is_url(s: str) -> bool:
    if not _is_str(s): 
        return False
    ss = s.strip().lower()
    return ss.startswith(("http://","https://","file://"))

def _upload_and_get_url(uploader: ImageUploader, path_or_url: str, what: str) -> str:
    if not _is_str(path_or_url):
        return ""
    if _is_url(path_or_url):
        return path_or_url
    res = uploader.upload_url_or_path(path_or_url)
    url = res.url or ""
    if not url or not _is_url(url):
        print(f"[WARN] Cannot upload image for {what}: {path_or_url} | provider={res.provider} ok={res.ok} err={res.error}")
        return ""
    return url

def attach_image_links_in_question(q: Dict[str, Any], uploader: ImageUploader) -> Dict[str, Any]:
    found = ok = 0

    # Question image
    qi = q.get("question_image")
    if _is_str(qi):
        found += 1
        url = _upload_and_get_url(uploader, qi, "question_image")
        if url:
            q["question_image_url"] = url
            ok += 1

    # Options
    for idx, opt in enumerate(q.get("options", [])):
        if isinstance(opt, dict) and _is_str(opt.get("option_image")):
            found += 1
            url = _upload_and_get_url(uploader, opt["option_image"], f"option_image[{idx}]")
            if url:
                opt["option_image_url"] = url
                ok += 1

    # Explanation
    exp = q.get("explanation")
    if isinstance(exp, dict) and _is_str(exp.get("image")):
        found += 1
        url = _upload_and_get_url(uploader, exp["image"], "explanation.image")
        if url:
            exp["image_url"] = url
            ok += 1

    if found:
        print(f"[attach_image_links] images_found={found} images_with_url={ok}")
    return q

def attach_image_links(data, uploader: ImageUploader):
    if isinstance(data, dict):
        return attach_image_links_in_question(data, uploader)
    if isinstance(data, list):
        cnt_found = cnt_ok = 0
        out = []
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                before = (cnt_found, cnt_ok)
                item = attach_image_links_in_question(item, uploader)
                # thô: do attach_image_links_in_question đã in, không cần tăng thêm
            out.append(item)
        return out
    return data
