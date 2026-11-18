import os
import json
from pathlib import Path
import tempfile
import unittest

from dekuforge.saves import discover_saves, game_save_profiles, import_save


class SaveDiscoveryTests(unittest.TestCase):
    def test_independent_native_profile_is_found_only_with_explicit_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp).resolve()
            executable = game/'DekuForgeGame.exe'
            executable.touch()
            (game/'.dekuforge-native').touch()
            profile = self.profile(game/'user/save'/('e'*32))
            self.assertEqual(game_save_profiles(executable), [])
            (game/'dekuforge-build-info.json').write_text(json.dumps({'save_layout': 'user/save'}))
            self.assertEqual([p['folder'] for p in game_save_profiles(executable)], [str(profile)])
            (game/'dekuforge-build-info.json').write_text(json.dumps({'save_layout': '../../outside'}))
            self.assertEqual(game_save_profiles(executable), [])

    def profile(self, folder, data=b'synthetic save'):
        (folder/'slot_00').mkdir(parents=True)
        (folder/'slot_00/progress.sav').write_bytes(data)
        return folder

    def test_nx_installation_root_finds_current_profiles_without_backups_or_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            current = self.profile(root/'NX2navi/Play/profile/save'/('a'*32))
            self.profile(root/'NX2navi/Play/profile/save-backup/old')
            self.profile(root/'NX2navi/Play/romfs/not-a-profile')
            result = discover_saves(root/'NX2navi')
            self.assertEqual([p['folder'] for p in result['profiles']], [str(current)])
            self.assertEqual(result['profiles'][0]['slots'], ['slot_00'])
            self.assertFalse(result['limited'])
            self.assertEqual(discover_saves(current)['profiles'], result['profiles'])

    def test_search_limits_and_multiple_profiles_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            old = self.profile(root/'first/profile')
            new = self.profile(root/'second/profile')
            os.utime(old/'slot_00/progress.sav', (100,100))
            os.utime(new/'slot_00/progress.sav', (200,200))
            result = discover_saves(root)
            self.assertEqual([p['folder'] for p in result['profiles']], [str(new),str(old)])
            self.assertTrue(discover_saves(root,max_entries=1)['limited'])
            self.assertTrue(discover_saves(root,max_depth=1)['limited'])

    def test_play_folder_is_searched_before_a_large_unrelated_source_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = self.profile(root/'Play/profile/save'/('d'*32))
            unrelated = root/'Contribute'; unrelated.mkdir()
            for i in range(30): (unrelated/f'code-{i}.txt').touch()
            result = discover_saves(root,max_entries=20)
            self.assertEqual([p['folder'] for p in result['profiles']], [str(source)])
            self.assertTrue(result['limited'])

    def test_destination_uses_owned_active_game_and_ignores_backup_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp).resolve()
            executable = game/'DekuForgeGame.exe'; executable.touch()
            profile = self.profile(game/'profile/save'/('b'*32))
            self.profile(game/'profile/save'/('b'*32+'.backup-old'))
            self.assertEqual(game_save_profiles(executable), [])
            (game/'.dekuforge-stable-build').touch()
            self.assertEqual([p['folder'] for p in game_save_profiles(executable)], [str(profile)])

    def test_discovered_source_is_copied_only_after_explicit_import_with_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = self.profile(root/'old/Play/profile/save'/('c'*32),b'old game progress')
            destination = self.profile(root/'new/user', b'new game progress')
            result = discover_saves(root/'old')
            self.assertEqual((destination/'slot_00/progress.sav').read_bytes(),b'new game progress')
            backup = import_save(result['profiles'][0]['folder'],destination)
            self.assertEqual((source/'slot_00/progress.sav').read_bytes(),b'old game progress')
            self.assertEqual((destination/'slot_00/progress.sav').read_bytes(),b'old game progress')
            self.assertEqual((backup/'slot_00/progress.sav').read_bytes(),b'new game progress')

    def test_linked_search_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve();target = self.profile(root/'real')
            link = root/'link'
            try: link.symlink_to(target, target_is_directory=True)
            except OSError: self.skipTest('Directory symlinks unavailable')
            with self.assertRaises(ValueError): discover_saves(link)
