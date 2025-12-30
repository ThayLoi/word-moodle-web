# -*- coding: utf-8 -*-
import base64, json, time
from nacl.signing import VerifyKey             # pip install pynacl
from nacl.exceptions import BadSignatureError

# DÁN PUBLIC KEY (base64) do thầy sinh bên dưới vào đây:
PUBLIC_KEY_B64 = "FSgCUGClVBh5At2qRZvPOAU3Zt4KoEo8/5cHrjTb0pA="

def _ts(iso_utc: str) -> float:
    import time as _t
    return _t.mktime(_t.strptime(iso_utc, "%Y-%m-%dT%H:%M:%SZ"))

def verify_license_string(lic_str: str, machine_id: str) -> dict:
    """
    lic_str: chuỗi base64url của {"payload": {...}, "signature": "..."}.
    Trả về: payload đã kiểm chứng. Ném lỗi nếu không hợp lệ.
    """
    obj = json.loads(base64.urlsafe_b64decode(lic_str + "==").decode("utf-8"))
    payload = obj["payload"]; sig_b64 = obj["signature"]

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    signature = base64.urlsafe_b64decode(sig_b64)

    vk = VerifyKey(base64.b64decode(PUBLIC_KEY_B64))
    try:
        vk.verify(body, signature)
    except BadSignatureError:
        raise ValueError("Chữ ký license không hợp lệ")

    if payload.get("machine_id") not in (machine_id, "*"):
        raise ValueError("License không dành cho máy này")

    now = time.time()
    if "valid_from" in payload and now < _ts(payload["valid_from"]):
        raise ValueError("Chưa đến thời gian hiệu lực")
    if "valid_to" in payload and now > _ts(payload["valid_to"]):
        raise ValueError("License đã hết hạn")

    return payload
