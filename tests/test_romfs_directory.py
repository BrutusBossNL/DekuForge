import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.nup import Archive, ArchiveError
from dekuforge.romfs_directory import extract_directory
from test_modules import game_archive


class DirectoryExtractionTests(unittest.TestCase):
    def test_streamed_extraction_and_hash_checked_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            archive, output = root / 'own.nup', root / 'output'
            game_archive(archive)
            original = archive.read_bytes()
            tree = extract_directory(archive, output)
            package = Archive(archive).packages[0]
            for relative, member in Archive(archive).tree(package.romfs):
                self.assertEqual(hashlib.sha256((tree / relative).read_bytes()).digest(), member.digest)
            with patch.object(Archive, 'chunks', side_effect=AssertionError('Verified files must be reused')):
                self.assertEqual(extract_directory(archive, output), tree)
            self.assertEqual(archive.read_bytes(), original)
            self.assertTrue((output / 'complete.json').is_file())
            self.assertFalse((output / '.extract.lock').exists())

    def test_interrupted_file_is_not_committed_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            archive, output = root / 'own.nup', root / 'output'
            game_archive(archive)
            def broken(*args, **kwargs):
                yield b'partial'
                raise ArchiveError('Injected checksum failure')
            with patch.object(Archive, 'chunks', broken):
                with self.assertRaisesRegex(ArchiveError, 'Injected'):
                    extract_directory(archive, output)
            self.assertFalse((output / 'complete.json').exists())
            self.assertEqual(list((output / 'romfs').iterdir()), [])
            self.assertFalse((output / '.extract.lock').exists())
            self.assertEqual(list(output.glob('*.part')), [])
            extract_directory(archive, output)
            self.assertTrue((output / 'complete.json').is_file())

    def test_same_size_corruption_is_repaired_before_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            archive, output = root / 'own.nup', root / 'output'
            game_archive(archive)
            tree = extract_directory(archive, output)
            target = tree / 'main.npdm'
            expected = target.read_bytes()
            target.write_bytes(b'x' * len(expected))
            extract_directory(archive, output)
            self.assertEqual(target.read_bytes(), expected)

    def test_unowned_output_and_held_lock_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            archive, output = root / 'own.nup', root / 'output'
            game_archive(archive)
            output.mkdir()
            keep = output / 'save.dat'
            keep.write_bytes(b'preserve')
            with self.assertRaises(ValueError):
                extract_directory(archive, output)
            self.assertEqual(keep.read_bytes(), b'preserve')
            extract_directory(archive, root / 'owned')
            lock = root / 'owned/.extract.lock'
            lock.write_text('another builder')
            with self.assertRaises(FileExistsError):
                extract_directory(archive, root / 'owned')
            self.assertEqual(lock.read_text(), 'another builder')
