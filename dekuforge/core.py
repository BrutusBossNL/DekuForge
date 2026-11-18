"""Local installation selection and process launching; no game modification."""

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "local" / "settings.json"


def load_settings(settings=SETTINGS):
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def load_installation(settings=SETTINGS):
    value = load_settings(settings).get("executable", "")
    return value if isinstance(value, str) else ""


def update_settings(changes, settings=SETTINGS):
    data = load_settings(settings)
    data.update(changes)
    settings.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(settings)


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
    update_settings({"executable": str(executable)}, settings)
    return executable


def launch(value):
    executable = validate_installation(value)
    from .open_engine_runtime import launch_options
    options = launch_options(executable)
    if options:
        return subprocess.Popen(options['args'], cwd=str(executable.parent), env=options['env'], shell=False)
    return subprocess.Popen([str(executable)], cwd=str(executable.parent), shell=False)
