"""Run the same interface with temporary, isolated browser-session storage."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Deployment configuration, never a visitor-controlled choice.
os.environ["NIGHTJAR_STORAGE_MODE"] = "session"
runpy.run_path(str(ROOT / "app/main.py"), run_name="__main__")
