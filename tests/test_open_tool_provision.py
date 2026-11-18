import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


spec = importlib.util.spec_from_file_location('open_tool_provision', Path(__file__).resolve().parents[1]/'tools/provision_open_tools.py')
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


class GenericToolExtractionTests(unittest.TestCase):
    def test_selected_dependency_only_and_changed_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            bundle = root/'tools.zip'
            with zipfile.ZipFile(bundle, 'w') as archive:
                archive.writestr('package/sdl/SDL3.dll', b'generic fixture')
                archive.writestr('package/engine/game.exe', b'excluded fixture')
            output = root/'local/build-tools/sdl'
            with patch.object(provision, 'ROOT', root):
                provision.unpack(bundle, 'package/sdl', output)
                self.assertEqual([p.name for p in output.iterdir()], ['SDL3.dll'])
                (output/'SDL3.dll').write_bytes(b'keep changed file')
                with self.assertRaisesRegex(ValueError, 'Existing generic tool differs'):
                    provision.unpack(bundle, 'package/sdl', output)
                self.assertEqual((output/'SDL3.dll').read_bytes(), b'keep changed file')

    def test_traversal_and_case_aliases_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for index, names in enumerate((['package/sdl/../../escape'], ['package/sdl/a', 'package/sdl/A'])):
                bundle = root/f'tools{index}.zip'
                with zipfile.ZipFile(bundle, 'w') as archive:
                    for name in names:
                        archive.writestr(name, b'fixture')
                with patch.object(provision, 'ROOT', root):
                    with self.assertRaises(ValueError):
                        provision.unpack(bundle, 'package/sdl', root/f'local/build-tools/sdl{index}')
            self.assertFalse((root/'escape').exists())
