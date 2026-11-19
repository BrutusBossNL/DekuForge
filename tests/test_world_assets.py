"""Regression checks for selecting local world markers and preserving mod priority."""
from pathlib import Path
import json
import struct
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.world_assets import ASSETS, ASSET_FOLDER, _raise_sizes, selected
from dekuforge.world_map_art import archive_replace


class WorldAssetTests(unittest.TestCase):
    def test_growing_a_map_layout_keeps_controller_prompt_offsets(self):
        archive = bytearray(256)
        struct.pack_into('<II', archive, 8, len(archive), 128)
        archive[128:132] = b'map!'
        archive[160:166] = b'prompt'
        members = [('map', 32, 128, 132), ('prompt', 48, 160, 166)]
        with patch('dekuforge.world_map_art.archive_nodes', return_value=members):
            modified = archive_replace(archive, 'map', lambda body: body + b' world')
        self.assertEqual(modified[160:166], b'prompt')
        lo, hi = struct.unpack_from('<II', modified, 40)
        self.assertEqual(modified[128+lo:128+hi], b'map! world')

    def test_size_increase_only_changes_the_matching_native_entry(self):
        table = b'RESTBL' + struct.pack('<IIII', 1, 128, 2, 0) + struct.pack('<IIII', 11, 21, 12, 22)
        result = _raise_sizes(table, {12: 4096})
        self.assertEqual(struct.unpack_from('<IIII', result, 22), (11, 21, 12, 4118))
        with self.assertRaisesRegex(ValueError, 'Missing size'):
            _raise_sizes(table, {10: 4096})

    def test_incomplete_local_assets_are_never_activated(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary).resolve()
            marker_id = 'a' * 20
            folder = game/ASSET_FOLDER
            cache = folder/marker_id
            for filename in ASSETS:
                item = cache/filename
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(b'test')
            receipt = folder/'current.json'
            receipt.write_text(json.dumps({'id': marker_id, 'size': dict.fromkeys(ASSETS, 4)}), encoding='utf-8')
            self.assertEqual(selected(game), cache)
            (cache/ASSETS[0]).write_bytes(b'incomplete')
            self.assertIsNone(selected(game))
