"""Launcher defaults and system-language selection."""
import locale
import os

DEFAULTS = {"language": "system", "check_updates": True, "hide_playing": True,
            "keep_cache": True, "update_channel": "stable"}


def system_language():
    if os.name == "nt":
        import ctypes
        code = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "en")
    else:
        code = locale.getlocale()[0] or "en"
    language = code.replace("-", "_").split("_")[0].lower()
    return language if language in ("en", "nl", "de", "es", "fr") else "en"


def resolve_language(choice):
    return system_language() if choice == "system" else choice if choice in ("en", "nl", "de", "es", "fr") else "en"
