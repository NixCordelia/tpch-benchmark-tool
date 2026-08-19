"""项目根目录入口，实现位于 src/。"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
os.chdir(_ROOT)
sys.path.insert(0, str(_SRC))
runpy.run_path(str(_SRC / "main.py"), run_name="__main__")
