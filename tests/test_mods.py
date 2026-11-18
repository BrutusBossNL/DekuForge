"""Local synthetic mod payloads only; no installed game or user archive is changed."""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dekuforge.mods import ModLibrary, digest, fnv, rebuild_code
from dekuforge.mod_archives import extract_archive, seven_zip


class ModTests(unittest.TestCase):
    def setUp(self):
        # Exercise the retained compatibility adapter in isolation, never select it
        # as the independent engine's actual code-mod build route.
        fixture = patch('dekuforge.mods.COMPONENTS', {'engine': {'backend': 'adapter-fixture'}})
        fixture.start()
        self.addCleanup(fixture.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.game = self.root/'game'
        self.game.mkdir()
        self.exe = self.game/'DekuForgeGame.exe'
        self.exe.write_bytes(b'original executable')
        self.library = ModLibrary(self.exe, running=lambda: False)

    def archive(self, name='Pack.zip', files=None):
        path = self.root/name
        with zipfile.ZipFile(path, 'w') as archive:
            for key, data in (files or {'Wrapper/My mod/romfs/Actor/test.txt':b'mod payload'}).items():
                archive.writestr(key, data)
        return path

    def add(self, name, payload=b'payload'):
        directory = self.library.folder/name/'romfs/Actor'
        directory.mkdir(parents=True)
        (directory/'test.txt').write_bytes(payload)

    def test_import_normalizes_wrappers_starts_off_and_preserves_original(self):
        archive = self.archive()
        before = digest(archive)
        self.assertEqual(self.library.import_mod(archive), 'Pack')
        mod, = self.library.scan()
        self.assertFalse(mod.enabled)
        self.assertFalse(mod.problem)
        self.assertFalse(mod.needs_layout)
        self.assertEqual((mod.folder/'romfs/Actor/test.txt').read_bytes(), b'mod payload')
        self.assertEqual(digest(archive), before)
        self.library.toggle('Pack')
        self.assertTrue(self.library.scan()[0].enabled)
        with self.assertRaisesRegex(ValueError, 'mods_exists'):
            self.library.import_mod(archive)

    def test_load_order_conflicts_toggle_and_unrelated_settings_preserved(self):
        original = '# keep comments\n[video]\nresolution = 1080p\n[cheats]\nbomb_arrows = 1\n'
        self.library.ini.write_text(original)
        self.add('Alpha', b'A')
        self.add('Beta', b'B')
        mods = self.library.scan()
        self.assertEqual(mods[1].conflicts, [('actor/test.txt', 'Alpha')])
        self.assertEqual(mods[0].conflict_peers['actor/test.txt'], ['Beta'])
        self.library.move('Beta', -1)
        self.assertEqual([m.name for m in self.library.scan()], ['Beta', 'Alpha'])
        self.assertEqual(self.library.scan()[1].conflicts, [('actor/test.txt', 'Beta')])
        self.library.toggle('Beta')
        self.assertFalse(self.library.scan()[0].enabled)
        self.assertFalse(self.library.scan()[1].conflicts)
        text = self.library.ini.read_text()
        self.assertTrue(text.startswith(original))
        self.assertIn('mods_disabled = Beta', text)
        self.assertIn('mods_rebuild = off', text)

    def test_manual_archives_are_imported_once_and_remain_off(self):
        self.library.folder.mkdir()
        source = self.archive()
        installed_archive = self.library.folder/source.name
        installed_archive.write_bytes(source.read_bytes())
        first = self.library.prepare()
        self.assertEqual([m.name for m in first], ['Pack'])
        self.assertFalse(first[0].enabled)
        self.assertEqual([m.name for m in self.library.prepare()], ['Pack'])
        self.assertTrue(installed_archive.is_file())
        # Losing only the library receipt must not overwrite/reimport the mod.
        (self.game/'.dekuforge-mod-imports.json').unlink()
        self.assertEqual([m.name for m in self.library.prepare()], ['Pack'])

    def test_manual_nested_folder_is_normalized_without_losing_metadata(self):
        folder = self.library.folder/'Nested'
        (folder/'Outer/Inner/romfs/Actor').mkdir(parents=True)
        (folder/'Outer/Inner/romfs/Actor/test.txt').write_text('payload')
        (folder/'keep.txt').write_text('keep me')
        self.assertTrue(self.library.scan()[0].needs_layout)
        self.library.prepare()
        self.assertTrue((folder/'romfs/Actor/test.txt').is_file())
        self.assertEqual((folder/'keep.txt').read_text(), 'keep me')

    def test_unchanged_archive_and_config_are_not_rewritten_on_play(self):
        self.library.folder.mkdir()
        source = self.archive()
        (self.library.folder/source.name).write_bytes(source.read_bytes())
        self.library.prepare()
        before = self.library.ini.stat().st_mtime_ns
        with patch('dekuforge.mods.digest', side_effect=AssertionError('unchanged archive rehashed')):
            self.library.prepare()
        self.assertEqual(self.library.ini.stat().st_mtime_ns, before)

    def test_zip_directory_limits_checked_before_allocating_members(self):
        source = self.archive()
        original = source.read_bytes()
        for count, size in ((50001, 1), (1, 65*1024**2)):
            data = bytearray(original)
            end = data.rfind(b'PK\x05\x06')
            struct.pack_into('<H', data, end+10, count)
            struct.pack_into('<L', data, end+12, size)
            source.write_bytes(data)
            target = self.root/f'limit-{count}'
            target.mkdir()
            with patch('dekuforge.mod_archives.zipfile.ZipFile', side_effect=AssertionError('allocated')):
                with self.assertRaisesRegex(ValueError, 'mods_import_limit'):
                    extract_archive(source, target)

    def test_valid_zip64_footer_and_truncated_archives(self):
        source = self.archive()
        original = source.read_bytes()
        end = original.rfind(b'PK\x05\x06')
        footer = struct.unpack_from('<4s4H2LH', original, end)
        large = struct.pack('<4sQ2H2L4Q', b'PK\x06\x06', 44, 45, 45, 0, 0,
                            footer[4], footer[4], footer[5], footer[6])
        locator = struct.pack('<4sLQL', b'PK\x06\x07', 0, end, 1)
        small = struct.pack('<4s4H2LH', b'PK\x05\x06', 0, 0, 65535, 65535,
                            0xffffffff, 0xffffffff, 0)
        source.write_bytes(original[:end]+large+locator+small)
        target = self.root/'zip64'
        target.mkdir()
        extract_archive(source, target)
        self.assertTrue((target/'Wrapper/My mod/romfs/Actor/test.txt').is_file())
        source.write_bytes(original[:10])
        target = self.root/'truncated'
        target.mkdir()
        with self.assertRaisesRegex(ValueError, 'mods_unsafe_archive'):
            extract_archive(source, target)

    def test_atmosphere_layout_and_selected_romfs_folder(self):
        archive = self.archive(files={'atmosphere/contents/0400486024DEC000/romfs/UI/test.txt': b'payload'})
        self.library.import_mod(archive)
        self.assertTrue((self.library.folder/'Pack/romfs/UI/test.txt').is_file())
        folder = self.root/'Direct/romfs'
        folder.mkdir(parents=True)
        (folder/'sample.txt').write_bytes(b'direct')
        self.library.import_mod(folder)
        self.assertEqual((self.library.folder/'Direct/romfs/sample.txt').read_bytes(), b'direct')

    def test_descriptions_and_mod_notices_survive_normalization(self):
        archive = self.archive(files={'Wrapper/romfs/Actor/sample.txt':b'asset',
                                     'Wrapper/mod.json':b'{"description":"Original test mod"}',
                                     'Wrapper/LICENSE.txt':b'Keep this notice'})
        self.library.import_mod(archive)
        self.assertEqual(self.library.scan()[0].description, 'Original test mod')
        self.assertEqual((self.library.folder/'Pack/metadata/Wrapper/LICENSE.txt').read_bytes(), b'Keep this notice')

    def test_bad_archives_are_atomic_and_never_write_outside_staging(self):
        bad_names = ('../escape.txt', '/escape.txt', 'C:/escape.txt', 'romfs/CON.txt',
                     'romfs/test.txt:ads', 'romfs/../escape.txt', 'romfs\\escape.txt')
        for index, name in enumerate(bad_names):
            archive = self.archive('Bad'+str(index)+'.zip', {name:b'bad'})
            if '\\' in name:
                # zipfile normalizes Windows separators while writing; simulate
                # an actual foreign ZIP containing the unsafe raw separator.
                archive.write_bytes(archive.read_bytes().replace(b'romfs/escape.txt', b'romfs\\escape.txt'))
            with self.assertRaises(ValueError):
                self.library.import_mod(archive)
        self.assertFalse(any(p.is_dir() for p in self.library.folder.iterdir()))
        self.assertFalse((self.root/'escape.txt').exists())
        self.assertEqual(self.exe.read_bytes(), b'original executable')

    def test_duplicate_case_collision_and_symlink_zip_are_rejected(self):
        archive = self.archive(files={'romfs/Actor/A.txt':b'A','romfs/Actor/a.txt':b'B'})
        with self.assertRaises(ValueError):
            self.library.import_mod(archive)
        link = zipfile.ZipInfo('romfs/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr(link, '../outside')
        with self.assertRaises(ValueError):
            self.library.import_mod(archive)

    def test_plugin_blocks_entire_mod_and_mutations_refuse_running_game(self):
        archive = self.archive(files={'romfs/sample.txt':b'data','exefs/subsdk9':b'plugin'})
        self.library.import_mod(archive)
        mod, = self.library.scan()
        self.assertEqual(mod.problem, 'mods_plugin')
        with self.assertRaisesRegex(ValueError, 'mods_plugin'):
            self.library.toggle(mod.name)
        self.add('Normal')
        self.library.running = lambda: True
        before = self.library.ini.read_bytes()
        with self.assertRaisesRegex(ValueError, 'mods_close_game'):
            self.library.toggle('Normal')
        self.assertEqual(self.library.ini.read_bytes(), before)

    def test_archive_provider_reports_missing_7zip_and_real_7z_import(self):
        archive = self.root/'Pack.7z'
        archive.write_bytes(b'not used by absent provider')
        with patch('dekuforge.mod_archives.seven_zip', return_value=None):
            with self.assertRaisesRegex(ValueError, 'mods_need_7zip'):
                self.library.import_mod(archive)
        tool = seven_zip()
        if not tool:
            return
        source = self.root/'Seven/romfs/Actor'
        source.mkdir(parents=True)
        (source/'test.txt').write_bytes(b'7z payload')
        archive.unlink()
        subprocess.run([tool, 'a', '-t7z', str(archive), 'romfs'], cwd=source.parent.parent,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=30)
        self.library.import_mod(archive)
        self.assertEqual((self.library.folder/'Pack/romfs/Actor/test.txt').read_bytes(), b'7z payload')

    def test_code_receipts_detect_changes_and_reject_wrong_or_unsupported_patches(self):
        archive = self.archive(files={'exefs/example.pchtxt':b'synthetic patch'})
        self.library.import_mod(archive)
        self.library.toggle('Pack')
        mod, = self.library.scan()
        name, path = next(iter(mod.code.items()))
        self.assertIn(name, self.library.pending_code())
        cache = self.game/'build-cache'
        cache.mkdir()
        (cache/'mod-code.json').write_text(json.dumps({name:digest(path)}))
        self.assertFalse(self.library.pending_code())
        for kind in ('other','unsupported'):
            (cache/'exefs.status').write_text(f'{fnv(name.encode())}\t{fnv(path.read_bytes())}\t{kind}\t-\trefused\n')
            with self.assertRaisesRegex(ValueError, 'mods_code_rejected'):
                self.library.check_code_status()
        (cache/'exefs.status').write_text(f'{fnv(name.encode())}\t{fnv(path.read_bytes())}\tcode\t-\t\n')
        self.library.check_code_status()
        path.write_bytes(b'edited patch')
        self.assertIn(name, self.library.pending_code())

    def test_failed_code_build_restores_executable_configuration_and_receipts(self):
        (self.game/'.dekuforge-stable-build').touch()
        source = self.root/'own.nup'
        source.write_bytes(b'synthetic archive')
        self.library.ini.write_text('resolution = 1080p\n')
        cache = self.game/'build-cache'
        cache.mkdir()
        (cache/'state.json').write_text('old state')
        profile = self.game/'profile/save'
        profile.mkdir(parents=True)
        (profile/'progress.sav').write_bytes(b'keep save')
        def failed(*_):
            self.exe.write_bytes(b'failed executable')
            self.library.ini.write_text('bad configuration')
            (cache/'state.json').write_text('bad state')
            (cache/'mod-code.json').write_text('bad receipt')
            raise RuntimeError('synthetic compiler failure')
        with patch('dekuforge.stable_engine.build_stable', side_effect=failed):
            with self.assertRaisesRegex(RuntimeError, 'synthetic compiler failure'):
                rebuild_code(self.library, source, lambda *_:None)
        self.assertEqual(self.exe.read_bytes(), b'original executable')
        self.assertEqual(self.library.ini.read_text(), 'resolution = 1080p\n')
        self.assertEqual((cache/'state.json').read_text(), 'old state')
        self.assertFalse((cache/'mod-code.json').exists())
        self.assertEqual((profile/'progress.sav').read_bytes(), b'keep save')
        self.assertFalse((self.game/'.dekuforge-mod-build.lock').exists())

    def test_import_failure_cannot_activate_a_half_installed_mod(self):
        with patch.object(self.library, '_write', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.library.import_mod(self.archive())
        self.assertFalse((self.library.folder/'Pack').exists())

    def test_save_profile_cannot_be_configured_as_a_mod_library(self):
        self.library.ini.write_text('mods_dir = profile/save\n')
        with self.assertRaisesRegex(ValueError, 'mods_external_dir'):
            ModLibrary(self.exe, running=lambda:False)

    def test_builder_success_without_patch_acceptance_restores_the_previous_game(self):
        archive = self.archive(files={'exefs/example.pchtxt':b'synthetic patch'})
        self.library.import_mod(archive)
        self.library.toggle('Pack')
        (self.game/'.dekuforge-stable-build').touch()
        source = self.root/'own.nup'
        source.write_bytes(b'synthetic')
        name, path = next(iter(self.library.scan()[0].code.items()))
        def build(*_):
            cache = self.game/'build-cache'
            cache.mkdir(exist_ok=True)
            self.exe.write_bytes(b'linked without accepted patch')
            (cache/'mod-code.json').write_text(json.dumps({name:digest(path)}))
            (cache/'exefs.status').write_text(f'{fnv(name.encode())}\t{fnv(path.read_bytes())}\tunsupported\t-\trejected\n')
            return self.exe
        with patch('dekuforge.stable_engine.build_stable', side_effect=build):
            with self.assertRaisesRegex(ValueError, 'mods_code_rejected'):
                rebuild_code(self.library, source, lambda *_:None)
        self.assertEqual(self.exe.read_bytes(), b'original executable')
        self.assertFalse((self.game/'build-cache/mod-code.json').exists())

    def test_cheat_receipts_validate_each_named_cheat_before_launch(self):
        archive = self.archive(files={'cheats/0123456789ABCDEF.txt':b'[Example]\n04000000 00000000 00000000\n'})
        self.library.import_mod(archive)
        self.library.toggle('Pack')
        cache = self.game/'build-cache'
        cache.mkdir()
        name, path = next(iter(self.library.scan()[0].code.items()))
        (cache/'mod-code.json').write_text(json.dumps({name:digest(path)}))
        for kind in ('unsupported', 'data'):
            (cache/'cheats.status').write_text(f'{fnv(b"Pack/Example")}\t00000000\t{kind}\t0\tnote\n')
            if kind == 'unsupported':
                with self.assertRaisesRegex(ValueError, 'mods_code_rejected'):
                    self.library.check_code_status()
            else:
                self.library.check_code_status()

    def test_other_build_code_is_identified_before_an_expensive_rebuild(self):
        exefs = self.game/'exefs'
        exefs.mkdir()
        header = bytearray(256)
        header[:4] = b'NSO0'
        header[64:96] = bytes(range(1,33))
        (exefs/'main').write_bytes(header)
        self.library.import_mod(self.archive(files={'exefs/foreign.pchtxt':b'@nsobid-FFFFFFFF\n@enabled\n'}))
        self.assertEqual(self.library.scan()[0].problem, 'mods_other_version')
        with self.assertRaisesRegex(ValueError, 'mods_other_version'):
            self.library.toggle('Pack')
