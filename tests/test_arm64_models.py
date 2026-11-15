from pathlib import Path
import random
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "local" / "devdeps"))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (UC_CPU_ARM64_MAX, UC_ARM64_REG_Q0, UC_ARM64_REG_NZCV,
                                UC_ARM64_REG_FPSR, UC_ARM64_REG_FPCR)

from dekuforge.arm64_models import decode_half_negate, negate_half_vector


class HalfPrecisionModelTests(unittest.TestCase):
    def test_model_matches_arm64_including_nan_bits_and_zero_upper_lanes(self):
        cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        cpu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
        cpu.mem_map(0x1000, 0x1000)
        edges = (0, 0x8000, 1, 0x3C00, 0x7C00, 0xFC00, 0x7E00, 0x7D00, 0xFFFF)
        patterns = [sum(value << (lane * 16) for lane in range(8)) for value in edges]
        randomizer = random.Random(2411)
        patterns += [randomizer.getrandbits(128) for _ in range(24)]
        for wide in (False, True):
            for source, target in ((2, 2), (1, 0)):
                word = 0x2EF8F800 | (int(wide) << 30) | (source << 5) | target
                self.assertEqual(decode_half_negate(word), (target, source, wide))
                cpu.mem_write(0x1000, struct.pack("<I", word))
                for control in (0, 1 << 19, 1 << 25, 1 << 26):
                    for pattern in patterns:
                        cpu.reg_write(UC_ARM64_REG_Q0 + target, (1 << 128) - 1)
                        cpu.reg_write(UC_ARM64_REG_Q0 + source, pattern)
                        cpu.reg_write(UC_ARM64_REG_NZCV, 0xA0000000)
                        cpu.reg_write(UC_ARM64_REG_FPSR, 0x0800001F)
                        cpu.reg_write(UC_ARM64_REG_FPCR, control)
                        flags = cpu.reg_read(UC_ARM64_REG_FPSR)
                        cpu.emu_start(0x1000, 0x1004, count=1)
                        self.assertEqual(cpu.reg_read(UC_ARM64_REG_Q0 + target), negate_half_vector(pattern, wide))
                        self.assertEqual(cpu.reg_read(UC_ARM64_REG_NZCV), 0xA0000000)
                        self.assertEqual(cpu.reg_read(UC_ARM64_REG_FPSR), flags)

    def test_adjacent_opcodes_are_not_silently_accepted(self):
        self.assertIsNone(decode_half_negate(0x6EF8FC42))
        self.assertIsNone(decode_half_negate(0x6EF0F842))
        with self.assertRaises(ValueError):
            negate_half_vector(-1, True)
