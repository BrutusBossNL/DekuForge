from pathlib import Path
import json
import string
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.i18n import LANGUAGES, MESSAGES, translate
from dekuforge.workflow import BuildRequest, Progress, duration, validate_destination, validate_source


class WorkflowTests(unittest.TestCase):
    def test_current_build_rebuild_requires_exact_owned_independent_provider(self):
        from dekuforge.open_engine import manifest
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            installed = root/'build/game'
            installed.mkdir(parents=True)
            exe = installed/'DekuForgeGame.exe'
            exe.touch()
            (installed/'.dekuforge-owned').touch()
            marker = installed/'.dekuforge-open-output.json'
            with patch('dekuforge.workflow.ROOT', root), patch('dekuforge.COMPONENTS', {'engine': {'backend': 'independent'}}):
                for content in ('{}', '{broken', json.dumps({'provider_revision': 'another'})):
                    marker.write_text(content)
                    with self.assertRaises(ValueError):
                        validate_destination(installed, str(exe))
                marker.write_text(json.dumps({'provider_revision': manifest('hookshot')['revision']}))
                self.assertEqual(validate_destination(installed, str(exe)), installed)
                for forbidden in (installed/'nested', installed.parent):
                    with self.assertRaises(ValueError):
                        validate_destination(forbidden, str(exe))
            with patch('dekuforge.workflow.ROOT', root), patch('dekuforge.COMPONENTS', {'engine': {'backend': 'stable'}}):
                with self.assertRaises(ValueError):
                    validate_destination(installed, str(exe))

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

    def test_provider_estimate_counts_down_and_is_replaced_by_newer_ones(self):
        progress = Progress()
        progress.begin(now=100)
        progress.update({"overall": 0.25}, now=110)
        self.assertEqual(progress.fraction(), 0.25)
        self.assertIsNone(progress.remaining(now=111))   # a fraction alone is not a measured time
        progress.update({"eta": 100}, now=120)
        self.assertEqual(progress.remaining(now=130), 90)
        progress.update({"eta": 80}, now=140)
        self.assertEqual(progress.remaining(now=150), 70)
        self.assertIsNone(progress.remaining(now=221))   # the estimate ran out: unknown again, never a negative time
        progress.finish(now=230)
        self.assertIsNone(progress.remaining(now=231))

    def test_provider_events_keep_the_stage_and_ignore_invalid_values(self):
        progress = Progress()
        progress.begin(now=100)
        progress.update({"phase": "generating", "done": 10, "total": 100}, now=150)
        progress.update({"eta": 500}, now=151)
        progress.update({"overall": 0.5}, now=152)
        self.assertEqual((progress.phase, progress.done, progress.total), ("generating", 10, 100))
        progress.update({"overall": 0.4}, now=153)
        self.assertEqual(progress.fraction(), 0.5)       # the bar never moves backwards
        for bad in ({"eta": float("nan")}, {"eta": -1}, {"eta": float("inf")}, {"eta": "soon"},
                    {"overall": 2}, {"overall": float("nan")}, {"overall": None}):
            progress.update(bad, now=154)
        self.assertEqual((progress.eta, progress.eta_at, progress.overall), (500, 151, 0.5))
        progress.begin(now=200)
        self.assertEqual((progress.eta, progress.overall, progress.fraction()), (None, 0, 0))

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
