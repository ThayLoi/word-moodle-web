# -*- coding: utf-8 -*-
import hashlib, subprocess

APP_ID = "MoodleQuestions"  # salt riêng cho app (không đổi giữa các bản)

def _reg_machine_guid() -> str:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        v, _ = winreg.QueryValueEx(k, "MachineGuid")
        return (v or "").strip()
    except Exception:
        return ""

def _wmi_uuid() -> str:
    try:
        ps = "Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            creationflags=0x08000000
        ).decode("utf-8", "ignore").strip()
        return out
    except Exception:
        return ""

def _fmt20(hx: str) -> str:
    s = hx.upper()[:20]
    return "-".join([s[i:i+5] for i in range(0, 20, 5)])

def get_machine_id() -> str:
    seeds = [APP_ID, _reg_machine_guid(), _wmi_uuid()]
    raw = "|".join([x for x in seeds if x])
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return _fmt20(h)
