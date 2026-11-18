"""Native register-offset memory instructions against an independent A64 oracle."""
import ctypes
import struct
import unittest

from dekuforge.independent_cpu import decode, emit_machine, UnsupportedInstruction
from test_independent_control import (BASE, State, assert_state, export, load_state,
                                      native_library, oracle)
from test_independent_memory import Region, Memory, DATA


def encoded(size, opcode, option, scaled, rn=2, rt=0, rm=1):
    return (0x38200800 | size << 30 | opcode << 22 | rm << 16 |
            option << 13 | scaled << 12 | rn << 5 | rt)


def cases():
    for size in range(4):
        for opcode in range(4):
            if opcode == 2 and size == 3 or opcode == 3 and size >= 2:
                continue
            for option in (2, 3, 6, 7):
                for scaled in (0, 1):
                    for rn in (2, 31):
                        for rt in (0, 1, 31):
                            for rm in (1, 31):
                                yield encoded(size, opcode, option, scaled, rn, rt, rm)


class RegisterMemoryTests(unittest.TestCase):
    def test_extended_indices_and_signed_loads_match_oracle(self):
        words = list(cases())
        sources = [emit_machine([word], BASE) for word in words]
        header = sources[0].split('int deku_machine', 1)[0]
        source = header + '\n'.join(export('int indexed_' + str(i) + text.split('int deku_machine', 1)[1],
                                          'indexed_' + str(i)) for i, text in enumerate(sources))
        cpu, arm, registers = oracle()
        data = (ctypes.c_uint8 * 4096)()
        mappings = (Region * 1)(Region(DATA, len(data), data, 3))
        memory = Memory(mappings, 1, 0)
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                item = decode(word)
                function = getattr(library, 'indexed_' + str(index))
                function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]
                cpu.mem_write(BASE, struct.pack('<I', word))
                cpu.ctl_remove_cache(BASE, BASE + 4)
                # UXTW ignores the high half; SXTW must extend from bit 31.
                indices = ((0, 1, 0xabcdef010000003f) if item.extension == 2 else
                           (0, 0xffffffff, 0xabc00000ffffffff) if item.extension == 6 else
                           (0, 1, 0xffffffffffffffff))
                for seed in (0, 0x80):
                    for offset in indices:
                        initial = bytes((seed+i) % 256 for i in range(len(data)))
                        data[:] = initial
                        cpu.mem_write(DATA, initial)
                        values = [0xfedcba9887654321+i for i in range(31)]
                        values[1], values[2] = offset, DATA+1024
                        state = State((ctypes.c_uint64 * 31)(*values), DATA+1024, BASE, 0xb0000000)
                        load_state(cpu, arm, registers, state)
                        cpu.emu_start(BASE, BASE+4, count=1)
                        done = ctypes.c_uint64()
                        label = f'{word:08x}/{seed}/{offset:x}'
                        self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 0, label)
                        self.assertEqual(done.value, 1)
                        assert_state(self, cpu, arm, registers, state, label)
                        self.assertEqual(bytes(data), bytes(cpu.mem_read(DATA,len(data))), label)

    def test_invalid_extensions_and_prfm_are_not_silently_treated_as_loads(self):
        for option in (0, 1, 4, 5):
            with self.assertRaises(UnsupportedInstruction):
                decode(encoded(3, 1, option, 0))
        for word in (encoded(3, 2, 3, 0), encoded(2, 3, 3, 0), encoded(3,1,3,0) | (1 << 26),
                     0xfd400040, 0xfc400040, 0x5c000000):
            with self.assertRaises(UnsupportedInstruction):
                decode(word)

    def test_address_wrap_is_checked_before_touching_memory(self):
        word = encoded(3, 0, 7, 1)
        source = export(emit_machine([word],BASE), 'deku_machine')
        data = (ctypes.c_uint8 * 16)(*b'abcdefghijklmnop')
        mappings = (Region * 1)(Region(DATA, 16, data, 3))
        memory = Memory(mappings,1,0)
        with native_library(self,source) as library:
            function = library.deku_machine
            function.argtypes = [ctypes.POINTER(State),ctypes.POINTER(Memory),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64)]
            state, done = State(pc=BASE), ctypes.c_uint64()
            state.x[0],state.x[1],state.x[2] = 42, 0xffffffffffffffff, 0
            before = bytes(state)
            self.assertEqual(function(ctypes.byref(state),ctypes.byref(memory),1,ctypes.byref(done)),3)
            self.assertEqual((bytes(state),bytes(data),done.value),(before,b'abcdefghijklmnop',0))
            self.assertEqual(memory.fault_address,0xfffffffffffffff8)
