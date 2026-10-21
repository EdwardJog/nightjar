import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).parent / "app/cloud_entry.py"), run_name="__main__")
