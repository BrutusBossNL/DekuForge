"""Source-only audit fixtures, never game files or generated game code."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from dekuforge.open_engine import manifest, stage, verified_files


def fixture(entries=None):
    entries = entries or {'LICENSE': b'fixture license\n', 'tools/build.ps1': b'fixture\r\n'}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, content in entries.items():
            archive.writestr('source-pin/'+name, content)
    data = stream.getvalue()
    files = {}
    for name, content in entries.items():
        if name.endswith('.ps1'):
            content = content.replace(b'\r\n', b'\n')
        files[name] = {'size':len(content), 'sha1':hashlib.sha1(
            b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()}
    return data, {'revision':'fixture-pin', 'archive_sha256':hashlib.sha256(data).hexdigest(),
                  'files':files, 'url':'https://example.invalid/source.zip'}


class OpenEngineSourceTests(unittest.TestCase):
    def test_record_pins_exact_candidate_and_remains_experimental(self):
        record = manifest()
        self.assertFalse(record['production_approved'])
        self.assertEqual(len(record['revision']),40)
        self.assertEqual(len(record['files']),900)
        self.assertIn('GPL',record['license'])
        for name in ('LICENSE','LICENSE-MIT','THIRD_PARTY_NOTICES.md'):
            self.assertIn(name,record['files'])

    def test_archive_and_canonical_git_blobs_both_verified(self):
        data, record = fixture()
        self.assertEqual(verified_files(data,record)['tools/build.ps1'],b'fixture\n')
        with self.assertRaisesRegex(ValueError,'identity'):
            verified_files(data+b'x',record)
        record['files']['LICENSE']['sha1']='0'*40
        with self.assertRaisesRegex(ValueError,'blob mismatch'):
            verified_files(data,record)

    def test_second_provider_retains_exact_gpl_source_identity(self):
        record=manifest('hookshot')
        self.assertEqual(record['revision'],'1c7e70bb035a7f45419b23882e73d7eb09b93e16')
        self.assertEqual(len(record['files']),2188)
        self.assertFalse(record['production_approved'])
        self.assertIn('GPL-3.0',record['license'])
        with self.assertRaisesRegex(ValueError,'Unknown'):
            manifest('../another-source')

    def test_traversal_case_alias_and_incomplete_archive_rejected(self):
        for entries in ({'../outside':b'a'}, {'A':b'a','a':b'b'}):
            data, record=fixture(entries)
            with self.assertRaises(ValueError):
                verified_files(data,record)
        data,record=fixture()
        record['files']['missing']={'size':0,'sha1':'0'*40}
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            verified_files(data,record)

    def test_cached_stage_revalidates_and_never_overwrites_changed_source(self):
        data,record=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            cache=root/'local/build-tools/open-engine-fixture-pin.zip'
            cache.parent.mkdir(parents=True)
            cache.write_bytes(data)
            with patch('dekuforge.open_engine.manifest',return_value=record), patch('dekuforge.open_engine.urlopen') as network:
                source=stage(root)
                self.assertEqual(stage(root),source)
                network.assert_not_called()
                (source/'LICENSE').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'changed'):
                    stage(root)
                self.assertEqual((source/'LICENSE').read_bytes(),b'changed')

    def test_unowned_destination_is_preserved(self):
        _,record=fixture()
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'build/open-engine-source-fixture-pin'
            target.mkdir(parents=True)
            (target/'keep.txt').write_text('keep')
            with patch('dekuforge.open_engine.manifest',return_value=record):
                with self.assertRaisesRegex(ValueError,'not owned'):
                    stage(directory)
            self.assertEqual((target/'keep.txt').read_text(),'keep')
