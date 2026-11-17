from pathlib import Path
import struct
import tempfile
import unittest

from dekuforge.independent_analysis import analyze_module, analyze_exefs
from test_modules import executable


class IndependentAnalysisTests(unittest.TestCase):
    def test_static_census_reports_unknown_instructions_without_claiming_gameplay(self):
        raw = bytearray(executable())
        # Hash flag off for this synthetic text mutation; real hash flags remain checked.
        struct.pack_into('<I', raw, 12, 0)
        offset = struct.unpack_from('<I', raw, 16)[0]
        struct.pack_into('<IIII', raw, offset, 0xd503201f, 0x91000400, 0xd65f03c0, 0)
        result = analyze_module(bytes(raw), 'main')
        self.assertEqual((result['supported_words'], result['unsupported_words']), (3, 1))
        self.assertEqual(result['operations'], {'add': 1, 'nop': 1, 'ret': 1})
        self.assertIn('not executable-code', result['scope'])

    def test_directory_analysis_uses_canonical_layout_and_never_changes_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            payload = executable(True)
            for name in ('main', 'sdk'):
                (directory / name).write_bytes(payload)
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            result = analyze_exefs(directory)
            self.assertFalse(result['playable'])
            self.assertFalse(result['writes_game_inputs'])
            self.assertEqual(set(result['source_sha256']),
                             {'independent_analysis.py', 'independent_cpu.py', 'modules.py', 'gameplan.py'})
            self.assertGreater(result['modules'][1]['base'], result['modules'][0]['base'])
            self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)
