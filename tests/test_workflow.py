from pathlib import Path
import string
import tempfile
import unittest

from dekuforge.i18n import LANGUAGES, MESSAGES, translate
from dekuforge.workflow import BuildRequest, Progress, duration, validate_destination, validate_source


class WorkflowTests(unittest.TestCase):
    def test_all_languages_have_complete_matching_placeholders(self):
        keys = set(MESSAGES["en"])
        for code in LANGUAGES:
            self.assertEqual(set(MESSAGES[code]), keys, code)
            for key in keys:
                fields = lambda text: {field for _, field, _, _ in string.Formatter().parse(text) if field}
                self.assertEqual(fields(MESSAGES[code][key]), fields(MESSAGES["en"][key]), (code, key))
                self.assertTrue(MESSAGES[code][key].strip())

    def test_unknown_duration_is_not_fabricated(self):
        progress = Progress()
        progress.begin(now=100)
        self.assertIsNone(progress.remaining(now=150))
        progress.update({"phase": "generating", "done": 10, "total": 100}, now=150)
        self.assertIsNone(progress.remaining(now=151))
        self.assertEqual(progress.remaining(now=160), 90)
        progress.update({"phase": "normalizing"}, now=170)
        self.assertIsNone(progress.remaining(now=180))
        progress.finish(now=190)
        self.assertEqual(progress.elapsed(now=999), 90)
        self.assertEqual(duration(3661), "01:01:01")

    def test_request_never_overwrites_selected_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "own.rom"
            source.write_bytes(b"NUP\x01" + b"\0" * 124)
            current = root / "current"
            current.mkdir()
            game = current / "game.exe"
            game.touch()
            for destination in (current, current / "nested", root):
                with self.assertRaises(ValueError):
                    validate_destination(destination, str(game))
            request = BuildRequest.create(source, root / "new", str(game))
            self.assertEqual(request.destination, root / "new")
            self.assertFalse(request.destination.exists())
            self.assertEqual(validate_source(source), source)

    def test_non_nup_rom_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder).resolve() / "own.z64"
            source.write_bytes(b"\x80\x37\x12\x40")
            with self.assertRaisesRegex(ValueError, "invalid_source"):
                validate_source(source)

    def test_translation_falls_back_only_for_unknown_language(self):
        self.assertEqual(translate("unknown", "play"), "Play")
        self.assertEqual(translate("fr", "elapsed", time="00:10"), "Écoulé : 00:10")
