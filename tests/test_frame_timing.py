"""Check the timing bridge instructions against an independent ARM64 engine."""
from pathlib import Path
import struct
import unittest
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_S0, UC_ARM64_REG_S8, UC_ARM64_REG_X9, UC_ARM64_REG_X10


class FrameTimingTests(unittest.TestCase):
    def test_both_consumers_read_the_same_sixty_hz_elapsed_step(self):
        source = Path(__file__).resolve().parents[1] / "engine_overrides/frame_timing_v111.txt"
        loads = [int(line.split()[-1], 16) for line in source.read_text().splitlines()
                 if line.startswith("site") and "@page" not in line]
        self.assertEqual(len(loads), 2)
        for fps in (17, 28, 30, 60, 120):
            expected = 60.0 / fps
            for instruction, register in zip(loads, (UC_ARM64_REG_S8, UC_ARM64_REG_S0)):
                cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
                cpu.mem_map(0x1000, 0x2000)
                cpu.mem_write(0x1000, struct.pack("<I", instruction))
                cpu.mem_write(0x2008, struct.pack("<f", expected))
                cpu.reg_write(UC_ARM64_REG_X9, 0x2000)
                cpu.reg_write(UC_ARM64_REG_X10, 0x2000)
                cpu.emu_start(0x1000, 0x1004)
                actual = struct.unpack("<f", struct.pack("<I", cpu.reg_read(register)))[0]
                self.assertAlmostEqual(actual, expected, places=6)
