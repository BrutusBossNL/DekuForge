import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "local" / "devdeps"))
sys.path.insert(0, str(ROOT / "engine" / "recomp"))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_CPU_ARM64_MAX, UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X30

spec = importlib.util.spec_from_file_location("dekuforge_lifter_test", ROOT / "engine_overrides" / "lifter.py")
extension = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extension)


class ReturnCompatibilityTests(unittest.TestCase):
    def test_authenticated_return_projection_against_unicorn(self):
        lifter = extension.Lifter(0x1000)
        for hint, instruction in ((0xD503233F, 0xD65F0BFF), (0xD503237F, 0xD65F0FFF)):
            for target in (0x1800, 0x1900, 0x1A00):
                cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
                cpu.ctl_set_cpu_model(UC_CPU_ARM64_MAX)
                cpu.mem_map(0x1000, 0x1000)
                cpu.mem_write(0x1000, struct.pack("<II", hint, instruction))
                cpu.reg_write(UC_ARM64_REG_SP, 0x4000)
                cpu.reg_write(UC_ARM64_REG_X30, target)
                cpu.emu_start(0x1000, target, count=2)
                emitted = lifter.lift(instruction, 0x1004)
                self.assertEqual(emitted.kind, "ret")
                self.assertEqual(cpu.reg_read(UC_ARM64_REG_PC), target)
                # Unsigned-address projection: do not claim signed-pointer bits
                # or authentication failures are modeled by this extension.
                self.assertEqual(lifter.lift(hint, 0x1000).kind, "op")

    def test_ordinary_return_is_preserved_and_unknown_variant_still_fails(self):
        lifter = extension.Lifter(0x1000)
        self.assertEqual(lifter.lift(0xD65F03C0, 0x1000).kind, "ret")
        with self.assertRaises(extension.Unsupported):
            lifter.lift(0xD65F0BFE, 0x1000)
