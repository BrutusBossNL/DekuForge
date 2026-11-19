"""Launcher defaults and system-language selection."""
import locale
import os

from . import COMPONENTS

stage = COMPONENTS['launcher'].get('stage')
DEFAULTS = {"language": "system", "check_updates": True, "hide_playing": True,
            "auto_update": False, "keep_cache": True,
            "update_channel": stage if stage in {'stable', 'experimental'} else 'preview'}


def system_locale():
    if os.name == "nt":
        import ctypes
        code = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "en")
    else:
        code = locale.getlocale()[0] or "en"
    return code


def system_language():
    language = system_locale().replace("-", "_").split("_")[0].lower()
    return language if language in ("en", "nl", "de", "es", "fr") else "en"


def resolve_language(choice):
    return system_language() if choice == "system" else choice if choice in ("en", "nl", "de", "es", "fr") else "en"
