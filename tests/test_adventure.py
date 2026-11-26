import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.adventure import ACCOUNT, TIME_FIELDS, load_adventure, newest_slot, read_save, tally
from dekuforge.i18n import LANGUAGES, MESSAGES, translate
from dekuforge.launcher_labels import ROWS


def save_bytes(end, entries):
    header = bytearray(struct.pack('<III', 0x01020304, 0x002D80EB, end) + bytes(28))
    records = [*entries, *[(k + 0x40000000, 0) for k in range((end - 40) // 8 - len(entries))]]
    return bytes(header) + b''.join(struct.pack('<II', *row) for row in records)


class AdventureTests(unittest.TestCase):
    def create_slot(self, profile, slot, saved=None, valid=True):
        folder = profile / f'slot_{slot:02d}'
        folder.mkdir(parents=True)
        (folder / 'progress.sav').write_bytes(
            save_bytes(0x175D8, [(0, 2), (0x04735978, 37)]) if valid else b'broken')
        if saved is not None:
            (folder / 'caption.sav').write_bytes(
                save_bytes(0x2A0, [(0, 2), *zip(TIME_FIELDS, (2026, 11, 10, 12, 0, saved))]))
        return folder

    def test_game_timestamp_beats_copied_file_time(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp).resolve()
            self.create_slot(profile, 4, 14)
            older = self.create_slot(profile, 0, 12)
            os.utime(older / 'progress.sav', (2000000000, 2000000000))
            self.create_slot(profile, 1, 19, valid=False)
            self.assertEqual(newest_slot(profile).name, 'slot_04')

    def test_fallback_timestamp_and_missing_caption(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp).resolve()
            self.create_slot(profile, 0, valid=False)
            self.create_slot(profile, 2)
            recent = self.create_slot(profile, 3)
            os.utime(recent / 'progress.sav', (2000000000, 2000000000))
            slot = newest_slot(profile)
            self.assertEqual(slot.name, 'slot_03')
            self.assertIsNone(slot.saved)
            self.assertEqual(slot.thumbnail, b'')

    def test_corrupt_container_and_duplicate_fields_rejected(self):
        with self.assertRaises(ValueError):
            read_save(save_bytes(0x2A0, [(7, 0), (7, 1)]), 0x2A0)
        with self.assertRaises(ValueError):
            read_save(save_bytes(0x2A0, [])[:-1], 0x2A0)

    def test_unsupported_build_and_unavailable_world_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp).resolve()
            self.create_slot(game / 'user' / 'save' / ACCOUNT, 0, 0)
            options = {'args': [str(game / 'game.exe'), 'image', '--romfs',
                                str(game / 'romfs'), '--user', str(game / 'user')]}
            with patch('dekuforge.open_engine_runtime.launch_options', return_value=None):
                self.assertIsNone(load_adventure(game / 'game.exe', 'nl'))
            with patch('dekuforge.open_engine_runtime.launch_options', return_value=options):
                recap = load_adventure(game / 'game.exe', 'nl')
            skulls, hearts, *_ = recap.groups[2]
            self.assertEqual((skulls.done, skulls.total, skulls.unknown), (37, 100, 0))
            self.assertEqual((hearts.done, hearts.total, hearts.unknown), (0, 36, 36))

    def test_unknown_goals_stay_in_denominator_and_labels_are_complete(self):
        rec = tally('example', (True, False, None))
        self.assertEqual((rec.done, rec.total, rec.unknown), (1, 3, 1))
        for language in LANGUAGES:
            for key in ROWS:
                if key.startswith('recap_'):
                    self.assertIn(key, MESSAGES[language])
            self.assertIn('37', translate(language, 'recap_completion', percent=37, done=37, total=100))
