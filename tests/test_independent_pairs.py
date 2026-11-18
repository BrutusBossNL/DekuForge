"""Original paired-memory execution compared with an independent A64 oracle."""
import ctypes
import struct
import unittest

from dekuforge.independent_cpu import decode, emit_c, emit_machine, UnsupportedInstruction
from test_independent_control import (BASE, State, assert_state, export, load_state,
                                      native_library, oracle)
from test_independent_memory import Region, Memory, DATA


def pair(opcode, load, mode, offset, rn=2, rt=0, rt2=1):
    return (0x28000000 | opcode << 30 | mode << 23 | int(load) << 22 |
            (offset & 127) << 15 | rt2 << 10 | rn << 5 | rt)


def cases():
    for opcode, load in ((0, False), (0, True), (1, True), (2, False), (2, True)):
        for mode in (1, 2, 3):
            for offset in (-64, -1, 0, 1, 63):
                for rn in (2, 31):
                    for rt, rt2 in ((0, 1), (31, 0), (0, 31), (0, 0), (31, 31), (2, 1), (0, 2)):
                        if load and rt == rt2 or mode != 2 and rn != 31 and rn in (rt, rt2):
                            continue
                        yield pair(opcode, load, mode, offset, rn, rt, rt2)


class PairInstructionTests(unittest.TestCase):
    def test_reserved_and_constrained_variants_are_rejected(self):
        words = [pair(3, True, 2, 0), pair(1, False, 2, 0), pair(2, True, 0, 0),
                 pair(2, True, 1, 0, rt2=0), pair(2, False, 3, 1, rt2=2),
                 pair(2, True, 1, 1, rt=2), pair(2, True, 2, 0) | 1 << 26]
        for word in words:
            with self.subTest(word=hex(word)), self.assertRaises(UnsupportedInstruction):
                decode(word)
        with self.assertRaises(UnsupportedInstruction):
            emit_c([pair(2, True, 2, 0)])

    def test_pair_modes_widths_signs_aliases_and_zero_register_against_oracle(self):
        words = list(cases())
        sources = [emit_machine([word], BASE) for word in words]
        header = sources[0].split('int deku_machine', 1)[0]
        source = header + '\n'.join(export('int pair_' + str(i) + text.split('int deku_machine', 1)[1],
                                          'pair_' + str(i)) for i, text in enumerate(sources))
        cpu, arm, registers = oracle()
        data = (ctypes.c_uint8 * 4096)()
        mappings = (Region * 1)(Region(DATA, len(data), data, 3))
        memory = Memory(mappings, 1, 0)
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                function = getattr(library, 'pair_' + str(index))
                function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]
                cpu.mem_write(BASE, struct.pack('<I', word))
                cpu.ctl_remove_cache(BASE, BASE + 4)
                for seed in (0, 0x80, 0xff):
                    initial = bytes((seed + i) % 256 for i in range(len(data)))
                    data[:] = initial
                    cpu.mem_write(DATA, initial)
                    values = [0xfedcba9887654321 + i for i in range(31)]
                    values[2] = DATA + 1024
                    state = State((ctypes.c_uint64 * 31)(*values), DATA + 1024, BASE, 0xa0000000)
                    load_state(cpu, arm, registers, state)
                    cpu.emu_start(BASE, BASE + 4, count=1)
                    done = ctypes.c_uint64()
                    label = f'{word:08x}/{seed}'
                    self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 0, label)
                    self.assertEqual(done.value, 1)
                    assert_state(self, cpu, arm, registers, state, label)
                    self.assertEqual(bytes(data), bytes(cpu.mem_read(DATA, len(data))), label)

    def test_second_element_fault_preserves_registers_writeback_and_first_store(self):
        words = [pair(2, False, 1, 2), pair(2, True, 3, 1)]
        sources = [emit_machine([word], BASE) for word in words]
        header = sources[0].split('int deku_machine', 1)[0]
        source = header + '\n'.join(export('int fault_' + str(i) + text.split('int deku_machine', 1)[1],
                                          'fault_' + str(i)) for i, text in enumerate(sources))
        data = (ctypes.c_uint8 * 16)(*b'abcdefghijklmnop')
        mappings = (Region * 1)(Region(DATA, 8, data, 3))
        memory = Memory(mappings, 1, 0)
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                function = getattr(library, 'fault_' + str(index))
                function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]
                state = State(pc=BASE)
                state.x[0], state.x[1], state.x[2] = 0x1234, 0x5678, DATA if index == 0 else DATA - 8
                before = bytes(state)
                done = ctypes.c_uint64(99)
                self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 3)
                self.assertEqual((done.value, bytes(state), bytes(data)), (0, before, b'abcdefghijklmnop'))
                self.assertEqual(memory.fault_address, DATA + 8)

    def test_stack_frame_pair_round_trip_across_adjacent_regions(self):
        # STP X0,X1,[SP,#-16]!; LDP X3,X4,[SP],#16; SVC #0.
        words = [pair(2, False, 3, -2, rn=31), pair(2, True, 1, 2, rn=31, rt=3, rt2=4), 0xd4000001]
        source = export(emit_machine(words, BASE), 'deku_machine')
        first, second = (ctypes.c_uint8 * 8)(), (ctypes.c_uint8 * 8)()
        mappings = (Region * 2)(Region(DATA, 8, first, 3), Region(DATA+8, 8, second, 3))
        memory = Memory(mappings, 2, 0)
        with native_library(self, source) as library:
            function = library.deku_machine
            function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                 ctypes.POINTER(ctypes.c_uint64)]
            for permissions in (1, 0, 3):
                mappings[1].permissions = permissions
                first[:] = b'abcdefgh'
                second[:] = b'ijklmnop'
                state, done = State(sp=DATA+16, pc=BASE), ctypes.c_uint64()
                state.x[0], state.x[1] = 0x123456789abcdef0, 0xfedcba9876543210
                before = bytes(state)
                status = function(ctypes.byref(state), ctypes.byref(memory), 10, ctypes.byref(done))
                if permissions != 3:
                    self.assertEqual((status, done.value, bytes(state)), (3, 0, before))
                    self.assertEqual(bytes(first)+bytes(second), b'abcdefghijklmnop')
                else:
                    self.assertEqual((status, done.value, state.pc, state.sp), (2, 2, BASE+8, DATA+16))
                    self.assertEqual((state.x[3], state.x[4]), (state.x[0], state.x[1]))
