from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from dekuforge.open_engine_cheat_lift import BUILD_ID, HOOKS, install

ROOT = Path(__file__).resolve().parents[1]


class IndependentCheatTests(unittest.TestCase):
    def test_hooks_require_matching_build_and_all_instruction_words(self):
        words = {address: word for address, word, _ in HOOKS}
        image = SimpleNamespace(word=words.__getitem__)
        lifter = SimpleNamespace(after={})
        install(lifter, image, 'another build')
        self.assertEqual(lifter.after, {})
        last_address, last_word, _ = HOOKS[-1]
        words[last_address] = 0
        with self.assertRaises(ValueError):
            install(lifter, image, BUILD_ID)
        self.assertEqual(lifter.after, {})
        words[last_address] = last_word
        install(lifter, image, BUILD_ID)
        for address, _, callback in HOOKS:
            self.assertIn(f'{callback}(c)', lifter.after[address])

    def test_sprint_timer_and_independent_bottles(self):
        compiler = shutil.which('clang') or shutil.which('cc')
        if not compiler:
            self.skipTest('A C compiler is required for the independent native fixture')
        with tempfile.TemporaryDirectory() as temporary:
            exe = Path(temporary) / ('fixture.exe' if os.name == 'nt' else 'fixture')
            subprocess.run([compiler, '-std=c11', '-I', str(ROOT),
                            str(ROOT / 'tests/independent_cheats_fixture.c'), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
