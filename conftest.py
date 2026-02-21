"""
Root conftest.py — fixes Python path for test discovery.
The backend code uses imports like `from services.x` and `from core.x`,
which expect `backend/` to be on sys.path.
"""

import sys
from pathlib import Path

# Add backend/ to sys.path so `from services.x` and `from core.x` resolve
backend_dir = str(Path(__file__).parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


    