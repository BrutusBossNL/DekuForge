"""Run an included engine tool with an explicitly selected script entry point."""

from pathlib import Path
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

root = Path(__file__).resolve().parent
if __name__ == "__main__":
    from dekuforge.engine_workspace import stage_engine
    engine = stage_engine()
    script = (engine / sys.argv[1]).resolve()
    if not script.is_relative_to(engine.resolve()):
        raise SystemExit("Engine script must be inside the included source tree")
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")
