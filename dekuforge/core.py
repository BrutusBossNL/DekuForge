"""Local installation selection and process launching; no game modification."""

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "local" / "settings.json"


def load_installation(settings=SETTINGS):
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
        value = data.get("executable", "")
        return value if isinstance(value, str) else ""
    except (OSError, ValueError, AttributeError):
        return ""


def validate_installation(value):
    if not value:
        raise ValueError("Kies eerst een bestaande game-installatie.")
    executable = Path(value).expanduser().resolve()
    if not executable.is_file():
        raise ValueError("Het gekozen programmabestand bestaat niet.")
    if os.name == "nt" and executable.suffix.lower() != ".exe":
        raise ValueError("Kies het .exe-bestand van de game.")
    return executable


def save_installation(value, settings=SETTINGS):
    executable = validate_installation(value)
    settings.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings.with_suffix(".tmp")
    temporary.write_text(json.dumps({"executable": str(executable)}, indent=2), encoding="utf-8")
    temporary.replace(settings)
    return executable


def launch(value):
    executable = validate_installation(value)
    return subprocess.Popen([str(executable)], cwd=str(executable.parent), shell=False)
