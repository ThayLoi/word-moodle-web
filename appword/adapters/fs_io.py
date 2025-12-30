from pathlib import Path
from shutil import copy2
def ensure_dir(p: str): Path(p).mkdir(parents=True, exist_ok=True)
def copy_file(src: str, dst: str): ensure_dir(str(Path(dst).parent)); copy2(src, dst)
