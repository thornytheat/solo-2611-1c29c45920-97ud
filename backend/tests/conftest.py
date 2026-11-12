"""pytest 引导：保证容器内(/app)与宿主机(backend/)两种 cwd 都能 import src/scripts。"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
