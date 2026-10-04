import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if sys.platform == "win32":
    source = Path(shutil.which("gcc")).resolve().parents[1] / "share" / "licenses"
else:
    source = Path("/usr/share/licenses")
if not source.is_dir():
    raise SystemExit(f"Native dependency licenses not found: {source}")
shutil.copytree(source, root / "vendor" / "runtime-licenses", dirs_exist_ok=True)
