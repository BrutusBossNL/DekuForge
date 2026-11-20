import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from dekuforge.open_game_build import claim, owned, provider_events


class ProviderProgressTests(unittest.TestCase):
    def test_both_provider_dialects_and_the_compile_estimate_are_read(self):
        self.assertEqual(provider_events('progress 0.250 Compiling\n', 'checking'),
                         ('checking', [('progress', {'overall': 0.25})]))
        self.assertEqual(provider_events('@@eta 1472\n', 'compile'), ('compile', [('progress', {'eta': 1472.0})]))
        self.assertEqual(provider_events('@@stage lift Translating the game\n', 'checking'),
                         ('lift', [('phase', {'phase': 'lift', 'done': 0, 'total': 0})]))
        self.assertEqual(provider_events('@@progress 0.5\n', 'lift'),
                         ('lift', [('progress', {'phase': 'lift', 'done': 0.5, 'total': 1})]))

    def test_other_output_carries_no_events(self):
        for line in ('progress\n', 'progress soon\n', 'progress 1.5 over\n', 'progress nan x\n', '@@eta\n', '@@eta many\n',
                     '@@stage\n', '@@progress 2\n', '@@file code_1.c 51.1 new\n', '@@plan 696 696\n',
                     '[log] progress 0.1 x\n', '  9909.7 MiB written (102595 files completed)\n', '\n'):
            self.assertEqual(provider_events(line, 'compile'), ('compile', []), line)


class OpenGameOwnershipTests(unittest.TestCase):
    def test_launcher_uses_provider_only_after_explicit_local_opt_in(self):
        from dekuforge.independent_engine import build
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            config = root/'config.json'
            with (patch('dekuforge.open_game_build.CONFIG', config),
                  patch('dekuforge.open_game_build.build', return_value=root/'game.exe') as provider,
                  patch('dekuforge.stable_engine.build_stable') as excluded):
                for flag in (False, 'true', 1):
                    config.write_text(json.dumps({'enable_launcher_build': flag}))
                    with self.assertRaisesRegex(RuntimeError, 'independent_backend_incomplete'):
                        build(root/'own.nup', Mock(), root/'output')
                    provider.assert_not_called()
                config.write_text(json.dumps({'enable_launcher_build': True}))
                self.assertEqual(build(root/'own.nup', Mock(), root/'output'), root/'game.exe')
                self.assertEqual(provider.call_args.args[0], root/'own.nup')
                self.assertEqual(provider.call_args.args[2], root/'output')
                excluded.assert_not_called()

    def test_nonempty_unowned_and_different_provider_are_never_claimed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            work = root/'work'
            claim(work, '.owner.json', {'provider': 'fixture'})
            (work/'compiled.o').write_bytes(b'preserve')
            claim(work, '.owner.json', {'provider': 'fixture'})
            with self.assertRaises(ValueError):
                claim(work, '.owner.json', {'provider': 'another'})
            self.assertEqual((work/'compiled.o').read_bytes(), b'preserve')
            unowned = root/'user'
            unowned.mkdir()
            (unowned/'save').write_bytes(b'keep')
            with self.assertRaises(ValueError):
                claim(unowned, '.owner.json', {'provider': 'fixture'})
            self.assertFalse((unowned/'.owner.json').exists())

    def test_output_root_parent_and_outside_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for candidate in (root, root.parent, root.parent/'outside'):
                with self.assertRaises(ValueError):
                    owned(candidate, root)
            self.assertEqual(owned(root/'game', root), root/'game')
