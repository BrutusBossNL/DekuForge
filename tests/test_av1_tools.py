import importlib.util
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('av1_builder', Path(__file__).resolve().parents[1] / 'tools/build_av1_decoder.py')
av1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av1)


class DecoderToolTests(unittest.TestCase):
    def test_meson_cache_changes_with_installation_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(av1, 'ROOT', root):
                base = root / 'local/build-tools/dav1d-dev'
                previous = av1.meson_build_path(base, base / 'previous', 'config')
                current = av1.meson_build_path(base, base / 'current', 'config')
                self.assertNotEqual(previous, current)
                self.assertNotEqual(current, base / 'build')
                self.assertEqual(current, av1.meson_build_path(base, base / 'current', 'config'))

    def test_archive_traversal_aliases_and_links_are_rejected(self):
        for names in (['../escape'], ['/absolute'], ['drive:name'], ['A', 'a'], ['linked']):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                for name in names:
                    info = zipfile.ZipInfo(name)
                    if name == 'linked':
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, b'fixture')
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    av1.unpack_zip(stream.getvalue(), Path(folder).resolve())

    def test_changed_cached_tool_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            av1.put(root, 'include/header.h', b'original')
            av1.put(root, 'include/header.h', b'original')
            with self.assertRaisesRegex(ValueError, 'differs'):
                av1.put(root, 'include/header.h', b'changed')
            self.assertEqual((root / 'include/header.h').read_bytes(), b'original')
