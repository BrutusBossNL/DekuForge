from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from dekuforge.mods import ModLibrary
from dekuforge.open_engine_mods import prepare_mods


class IndependentAssetModTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.game = self.root/'build/game'
        self.game.mkdir(parents=True)
        self.exe = self.game/'DekuForgeGame.exe'
        self.exe.write_bytes(b'fixture executable')
        (self.game/'.dekuforge-runtime.json').write_text('{}')
        self.library = ModLibrary(self.exe, running=lambda: False)
        self.options = {'args': [str(self.exe)], 'env': {'KEEP': 'yes'}}
        for name, content in [('A', b'first priority'), ('B', b'second priority')]:
            path = self.game/'mods'/name/'romfs/Actor/item.txt'
            path.parent.mkdir(parents=True)
            path.write_bytes(content)

    def prepare(self):
        return prepare_mods(self.exe, self.options, self.root)

    def test_enabled_priority_and_disable_match_launcher_without_touching_assets(self):
        vanilla = self.game/'romfs/Actor/item.txt'
        vanilla.parent.mkdir(parents=True)
        vanilla.write_bytes(b'vanilla')
        first = self.prepare()
        snapshot = Path(first['env']['HOS_MODS'])
        self.assertEqual((snapshot/'DekuForge/romfs/Actor/item.txt').read_bytes(), b'first priority')
        self.assertEqual(self.prepare(), first)
        self.library.toggle('A')
        second = self.prepare()
        self.assertEqual((Path(second['env']['HOS_MODS'])/'DekuForge/romfs/Actor/item.txt').read_bytes(), b'second priority')
        self.library.toggle('B')
        self.assertEqual(Path(self.prepare()['env']['HOS_MODS']).name, 'disabled')
        self.assertEqual(vanilla.read_bytes(), b'vanilla')
        self.assertEqual(self.options['env'], {'KEEP': 'yes'})
        self.assertTrue((self.game/'dekuforge-mods.ini').is_file())
        self.assertFalse((self.game/'nx2navi.ini').exists())

    def test_changed_snapshot_is_refused_and_changed_source_gets_new_snapshot(self):
        first = self.prepare()
        target = Path(first['env']['HOS_MODS'])/'DekuForge/romfs/Actor/item.txt'
        target.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'mods_unsafe_archive'):
            self.prepare()
        source = self.game/'mods/A/romfs/Actor/item.txt'
        source.write_bytes(b'new mod data')
        second = self.prepare()
        self.assertNotEqual(first['env']['HOS_MODS'], second['env']['HOS_MODS'])
        self.assertEqual((Path(second['env']['HOS_MODS'])/'DekuForge/romfs/Actor/item.txt').read_bytes(), b'new mod data')

    def test_user_map_mod_has_priority_over_world_markers(self):
        from dekuforge.world_extra import MAP
        mod = self.game/'mods/A/romfs'/MAP
        mod.parent.mkdir(parents=True)
        mod.write_bytes(b'user map')
        self.options['env'].update(DEKUFORGE_WORLD_DATA='world cache', HOS_FS_OVERLAY='overlay')
        chosen = self.prepare()['env']
        self.assertNotIn('DEKUFORGE_WORLD_DATA', chosen)
        self.assertNotIn('HOS_FS_OVERLAY', chosen)
        self.assertEqual((Path(chosen['HOS_MODS'])/'DekuForge/romfs'/MAP).read_bytes(), b'user map')
        self.library.toggle('A')
        self.assertEqual(self.prepare()['env']['DEKUFORGE_WORLD_DATA'], 'world cache')

    def test_code_mods_are_gated_and_external_game_is_refused(self):
        code = SimpleNamespace(enabled=True, problem='', code={'test': Path('fixture.txt')})
        with patch('dekuforge.open_engine_mods.ModLibrary.scan', return_value=[code]):
            with self.assertRaisesRegex(ValueError, 'independent_backend_incomplete'):
                self.prepare()
        with self.assertRaisesRegex(ValueError, 'mods_external_dir'):
            prepare_mods(self.root/'external.exe', self.options, self.root)

    def test_runtime_path_limit_is_reported_before_snapshot_is_created(self):
        # Exercise the engine limit regardless of the OS's temporary-root length.
        prefix = str(self.game/'.dfmods'/('0'*20)/'DekuForge/romfs')
        length = max(12, 260-len(prefix.encode('utf-8'))+8)
        long_file = self.game/'mods/A/romfs'/('x'*(length-4)+'.txt')
        long_file.write_bytes(b'fixture')
        with self.assertRaisesRegex(ValueError, 'mods_path_too_long'):
            self.prepare()
        self.assertFalse((self.game/'.dfmods').exists())
