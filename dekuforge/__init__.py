"""DekuForge: original launcher and game-tooling foundation."""

import json
from pathlib import Path

COMPONENTS = json.loads(Path(__file__).with_name("components.json").read_text(encoding="utf-8"))
__version__ = COMPONENTS["launcher"]["version"]
