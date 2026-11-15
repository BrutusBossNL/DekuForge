"""Execute a separately installed builder without importing or bundling its code."""

from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    script = Path(sys.argv[1]).resolve()
    dependencies = Path(sys.argv[2]).resolve()
    arguments = sys.argv[3:]
    sys.path.insert(0, str(dependencies))
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *arguments]
    runpy.run_path(str(script), run_name="__main__")
