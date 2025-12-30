import json
from pathlib import Path
_DEFAULT = {"image_dir":"images","author":"GV Huỳnh Văn Lợi","kprime_lowercase_option":True}
def load_config(path: str | None):
    if not path: return dict(_DEFAULT)
    p=Path(path)
    if not p.exists(): return dict(_DEFAULT)
    try: return {**_DEFAULT, **json.loads(p.read_text(encoding="utf-8"))}
    except Exception: return dict(_DEFAULT)
