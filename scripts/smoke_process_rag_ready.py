from pathlib import Path
import runpy

BACKEND_SCRIPT = (
    Path(__file__).resolve().parents[1] / "backend" / "scripts" / "preflight_folder.py"
)
runpy.run_path(str(BACKEND_SCRIPT), run_name="__main__")
