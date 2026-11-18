import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.core import launch
from dekuforge.open_engine_runtime import MANIFEST, game_language, launch_options


class IndependentRuntimeTests(unittest.TestCase):
    def test_game_language_keeps_supported_regions_and_falls_back_to_english(self):
        for local, expected in [('nl_NL', 'nl'), ('fr_CA', 'fr-CA'), ('es-MX', 'es-419'),
                                ('zh_HK', 'zh-Hant'), ('ja_JP', 'ja'), ('sv_SE', 'en-US')]:
            with self.subTest(locale=local):
                self.assertEqual(game_language(local), expected)

    def fixture(self, root):
        game = root / 'build/native'
        game.mkdir(parents=True)
        exe = game / 'DekuForgeGame.exe'
        exe.touch()
        image = game / 'image.bin'
        image.write_bytes(b'synthetic image')
        for name in ('romfs', 'user'):
            (game / name).mkdir()
        record = {'schema': 1, 'backend': 'hookshot-gpl', 'executable': exe.name,
                  **{key: str(game / value) for key, value in [('image', 'image.bin'), ('romfs', 'romfs'), ('user', 'user')]}}
        (game / MANIFEST).write_text(json.dumps(record))
        return exe, record

    def test_explicit_resources_and_clean_environment_reach_child(self):
        with tempfile.TemporaryDirectory(prefix='deku test ') as folder:
            root = Path(folder).resolve()
            exe, record = self.fixture(root)
            with patch.dict('os.environ', {'HOS_CONTROL_MEM': '1', 'RX_BACKEND': 'legacy', 'KEEP_ME': 'yes'}):
                options = launch_options(exe, root)
            self.assertEqual(options['args'], [str(exe), record['image'], '--romfs', record['romfs'], '--user', record['user']])
            self.assertEqual(options['env']['RX_BACKEND'], 'vulkan')
            self.assertEqual(options['env']['RX_VK_LOAD'], 'start')
            self.assertNotIn('HOS_CONTROL_MEM', options['env'])
            self.assertEqual(options['env']['KEEP_ME'], 'yes')
            with (patch('dekuforge.open_engine_runtime.launch_options', return_value=options),
                  patch('dekuforge.open_engine_mods.prepare_mods', side_effect=lambda exe, opts: opts),
                  patch('dekuforge.core.subprocess.Popen') as popen):
                launch(str(exe))
                popen.assert_called_once_with(options['args'], cwd=str(exe.parent), env=options['env'], shell=False)

    def test_wrong_identity_external_resource_and_missing_image_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            exe, record = self.fixture(root)
            for key, value in [('backend', 'legacy'), ('executable', 'another.exe'), ('romfs', str(root)), ('image', str(exe.parent / 'absent.bin'))]:
                bad = {**record, key: value}
                (exe.parent / MANIFEST).write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    launch_options(exe, root)

    def test_custom_game_without_metadata_keeps_existing_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(launch_options(Path(folder) / 'game.exe', Path(folder)))
