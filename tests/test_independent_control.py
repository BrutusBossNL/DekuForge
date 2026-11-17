"""Native execution against Unicorn, including overflow and branch truth tables."""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest

from dekuforge.independent_cpu import HEADER, decode, emit_c, emit_program

BASE = 0x10000


class State(ctypes.Structure):
    _fields_ = [('x', ctypes.c_uint64 * 31), ('sp', ctypes.c_uint64),
                ('pc', ctypes.c_uint64), ('nzcv', ctypes.c_uint64)]


@contextmanager
def native_library(test, source):
    compiler = os.environ.get('DEKUFORGE_TEST_CC') or shutil.which('clang') or shutil.which('cc')
    if not compiler:
        test.skipTest('C compiler unavailable')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        code = root / 'test.c'
        code.write_text(source, encoding='utf-8')
        output = root / ('test.dll' if os.name == 'nt' else 'test.so')
        command = [compiler, '-std=c11', '-O2', '-shared', str(code), '-o', str(output)]
        if os.name != 'nt':
            command.insert(1, '-fPIC')
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        test.assertEqual(result.returncode, 0, result.stderr)
        library = ctypes.CDLL(str(output))
        try:
            yield library
        finally:
            if os.name == 'nt':
                import _ctypes
                _ctypes.FreeLibrary(library._handle)


def export(source, name):
    prefix = '__declspec(dllexport) ' if os.name == 'nt' else ''
    return source.replace('int ' + name + '(', prefix + 'int ' + name + '(')


def oracle():
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
    import unicorn.arm64_const as arm
    cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    cpu.mem_map(0x1000, 0x40000)
    return cpu, arm, [getattr(arm, 'UC_ARM64_REG_X' + str(i)) for i in range(31)]


def load_state(cpu, arm, registers, state):
    for register, value in zip(registers, state.x):
        cpu.reg_write(register, value)
    cpu.reg_write(arm.UC_ARM64_REG_SP, state.sp)
    cpu.reg_write(arm.UC_ARM64_REG_NZCV, state.nzcv)
    cpu.reg_write(arm.UC_ARM64_REG_PC, state.pc)


def assert_state(test, cpu, arm, registers, state, label):
    test.assertEqual(list(state.x), [cpu.reg_read(r) for r in registers], label)
    test.assertEqual(state.sp, cpu.reg_read(arm.UC_ARM64_REG_SP), label)
    test.assertEqual(state.pc, cpu.reg_read(arm.UC_ARM64_REG_PC), label)
    test.assertEqual(state.nzcv, cpu.reg_read(arm.UC_ARM64_REG_NZCV), label)


def instruction_cases():
    words = []
    for wide in (0, 1):
        width = 64 if wide else 32
        for sub in (0, 1):
            for flags in (0, 1):
                for rd, rn in ((0, 0), (1, 0), (31, 0), (0, 31), (31, 31)):
                    for immediate in (0, 1, 4095):
                        for shift in (0, 1):
                            words.append(0x11000000 | wide << 31 | sub << 30 | flags << 29 |
                                         shift << 22 | immediate << 10 | rn << 5 | rd)
                for mode in range(3):
                    for shift in (0, 1, width - 1):
                        for rd, rn, rm in ((0, 0, 1), (0, 0, 0), (31, 0, 1), (0, 31, 1), (0, 1, 31)):
                            words.append(0x0b000000 | wide << 31 | sub << 30 | flags << 29 |
                                         mode << 22 | rm << 16 | shift << 10 | rn << 5 | rd)
        for opcode in range(4):
            for invert in (0, 1):
                for mode in range(4):
                    for shift in (0, 1, width - 1):
                        for rd, rn, rm in ((0, 0, 1), (31, 0, 1), (0, 31, 1), (0, 1, 31)):
                            words.append(0x0a000000 | wide << 31 | opcode << 29 | mode << 22 |
                                         invert << 21 | rm << 16 | shift << 10 | rn << 5 | rd)
        for opcode in (0, 2, 3):
            for shift in range(width // 16):
                for rd in (0, 31):
                    for immediate in (0, 1, 65535):
                        words.append(0x12800000 | wide << 31 | opcode << 29 |
                                     shift << 21 | immediate << 5 | rd)
    for page in (0, 1):
        for offset in (0, 1, -1, 0xfffff, -0x100000):
            immediate = offset & 0x1fffff
            words.append(0x10000000 | page << 31 | (immediate & 3) << 29 | (immediate >> 2) << 5)
    return list(dict.fromkeys(words))


class NativeIntegerTests(unittest.TestCase):
    def test_integer_flags_shifts_and_addresses_against_oracle(self):
        words = instruction_cases()
        functions = [emit_c([word], BASE).split('int deku_block', 1)[1] for word in words]
        source = HEADER + '\n'.join(export('int case_' + str(i) + body, 'case_' + str(i))
                                    for i, body in enumerate(functions))
        cpu, arm, registers = oracle()
        edges = (0, 1, 0x7fffffff, 0x80000000, 0xffffffff,
                 0x7fffffffffffffff, 0x8000000000000000, 0xffffffffffffffff)
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                function = getattr(library, 'case_' + str(index))
                function.argtypes = [ctypes.POINTER(State)]
                function.restype = ctypes.c_int
                cpu.mem_write(BASE, struct.pack('<I', word))
                cpu.ctl_remove_cache(BASE, BASE + 4)
                for iteration, value in enumerate(edges):
                    values = [value] * 31
                    values[1] = edges[(iteration + 3) % len(edges)]
                    state = State((ctypes.c_uint64 * 31)(*values), value, BASE, (iteration % 16) << 28)
                    load_state(cpu, arm, registers, state)
                    cpu.emu_start(BASE, BASE + 4, count=1)
                    self.assertEqual(function(ctypes.byref(state)), 0)
                    assert_state(self, cpu, arm, registers, state, f'{word:08x}/{iteration}')

    def test_branches_all_conditions_and_link_aliases_against_oracle(self):
        words = []
        for offset in (0, 4, -4, 32, -32):
            words += [0x14000000 | ((offset // 4) & 0x3ffffff),
                      0x94000000 | ((offset // 4) & 0x3ffffff)]
            words += [0x54000000 | (((offset // 4) & 0x7ffff) << 5) | condition for condition in range(16)]
            for wide in (0, 1):
                for nonzero in (0, 1):
                    for register in (0, 31):
                        words.append(0x34000000 | wide << 31 | nonzero << 24 |
                                     ((offset // 4) & 0x7ffff) << 5 | register)
            for bit in (0, 31, 32, 63):
                for nonzero in (0, 1):
                    words.append(0x36000000 | (bit // 32) << 31 | nonzero << 24 |
                                 (bit % 32) << 19 | ((offset // 4) & 0x3fff) << 5)
        for opcode in (0xd61f0000, 0xd63f0000, 0xd65f0000):
            words += [opcode | register << 5 for register in (0, 30)]
        functions = [emit_c([word], BASE).split('int deku_block', 1)[1] for word in words]
        source = HEADER + '\n'.join(export('int branch_' + str(i) + body, 'branch_' + str(i))
                                    for i, body in enumerate(functions))
        cpu, arm, registers = oracle()
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                function = getattr(library, 'branch_' + str(index))
                function.argtypes = [ctypes.POINTER(State)]
                cpu.mem_write(BASE, struct.pack('<I', word))
                cpu.ctl_remove_cache(BASE, BASE + 4)
                for flags in range(16):
                    values = [0x11000] * 31
                    if decode(word).operation not in {'br', 'blr', 'ret'}:
                        values[0] = (0, 1, 0x80000000, 0x8000000000000000)[flags % 4]
                    state = State((ctypes.c_uint64 * 31)(*values), 0x30000, BASE, flags << 28)
                    load_state(cpu, arm, registers, state)
                    cpu.emu_start(BASE, BASE + 4, count=1)
                    self.assertEqual(function(ctypes.byref(state)), 0)
                    assert_state(self, cpu, arm, registers, state, f'{word:08x}/NZCV={flags:x}')

    def test_native_program_loop_call_and_budget_resume(self):
        # MOVZ x0,5; MOVZ x1,0; ADD x1,x1,x0; SUBS x0,x0,1;
        # B.NE -8; BL +8; B +12; ADD x1,x1,1; RET; NOP
        words = [0xd28000a0, 0xd2800001, 0x8b000021, 0xf1000400,
                 0x54ffffc1, 0x94000002, 0x14000003, 0x91000421, 0xd65f03c0, 0xd503201f]
        source = export(emit_program(words, BASE), 'deku_run')
        cpu, arm, registers = oracle()
        randomizer = random.Random(17112026)
        state = State((ctypes.c_uint64 * 31)(*[randomizer.getrandbits(64) for _ in range(31)]), 0x30000, BASE, 0)
        load_state(cpu, arm, registers, state)
        cpu.mem_write(BASE, struct.pack('<' + 'I' * len(words), *words))
        with native_library(self, source) as library:
            run = library.deku_run
            run.argtypes = [ctypes.POINTER(State), ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)]
            done = ctypes.c_uint64()
            for budget in (0, 1, 2, 7, 4, 8):
                before = bytes(state)
                self.assertEqual(run(ctypes.byref(state), budget, ctypes.byref(done)), 0)
                self.assertEqual(done.value, budget)
                if not budget:
                    self.assertEqual(bytes(state), before)
                else:
                    cpu.emu_start(cpu.reg_read(arm.UC_ARM64_REG_PC) or BASE, BASE + len(words) * 4, count=budget)
                assert_state(self, cpu, arm, registers, state, f'budget {budget}')
            self.assertEqual(state.x[1], 16)
            self.assertEqual(run(ctypes.byref(state), 1, ctypes.byref(done)), 1)
            self.assertEqual(done.value, 0)

    def test_service_traps_and_unknown_pc_never_silently_continue(self):
        source = export(emit_program([0xd2800020, 0xd40000e1], BASE), 'deku_run')
        with native_library(self, source) as library:
            run = library.deku_run
            run.argtypes = [ctypes.POINTER(State), ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)]
            state = State(pc=BASE)
            done = ctypes.c_uint64()
            self.assertEqual(run(ctypes.byref(state), 10, ctypes.byref(done)), 2)
            self.assertEqual((done.value, state.x[0], state.pc), (1, 1, BASE + 4))
            before = bytes(state)
            self.assertEqual(run(ctypes.byref(state), 10, ctypes.byref(done)), 2)
            self.assertEqual(bytes(state), before)
            state.pc += 1
            before = bytes(state)
            self.assertEqual(run(ctypes.byref(state), 10, ctypes.byref(done)), 1)
            self.assertEqual((done.value, bytes(state)), (0, before))
