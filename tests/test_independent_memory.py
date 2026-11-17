"""Native scalar memory execution checked against ARM64 and fault boundaries."""
import ctypes
import struct
import unittest

from dekuforge.independent_cpu import decode, emit_machine, emit_c, UnsupportedInstruction
from dekuforge.gameplan import FIRST_ADDRESS
from dekuforge.guest_memory import AddressSpace
from test_independent_control import (BASE, State, assert_state, export, load_state,
                                      native_library, oracle)

DATA = 0x20000


class Region(ctypes.Structure):
    _fields_ = [('base', ctypes.c_uint64), ('size', ctypes.c_uint64),
                ('data', ctypes.POINTER(ctypes.c_uint8)), ('permissions', ctypes.c_uint32)]


class Memory(ctypes.Structure):
    _fields_ = [('regions', ctypes.POINTER(Region)), ('count', ctypes.c_uint64),
                ('fault_address', ctypes.c_uint64)]


def cases():
    words = []
    for size in range(4):
        for opcode in range(4):
            if opcode >= 2 and (size == 3 or opcode == 3 and size >= 2):
                continue
            for rd, rn in ((0, 2), (31, 2), (0, 31), (2, 2)):
                for immediate in (0, 1, 31):
                    words.append(0x39000000 | size << 30 | opcode << 22 |
                                 immediate << 10 | rn << 5 | rd)
                for mode in (0, 1, 3):
                    if mode and rn == rd and rn != 31:
                        continue
                    for immediate in (-256, -1, 0, 1, 255):
                        words.append(0x38000000 | size << 30 | opcode << 22 |
                                     (immediate & 511) << 12 | mode << 10 | rn << 5 | rd)
    for opcode in range(3):
        for rd in (0, 31):
            for offset in (-128, 128):
                words.append(0x18000000 | opcode << 30 | ((offset // 4) & 0x7ffff) << 5 | rd)
    return list(dict.fromkeys(words))


class NativeMemoryTests(unittest.TestCase):
    def test_load_relocate_and_execute_synthetic_module_to_service_boundary(self):
        words = [0x10010002, 0xd2800540, 0xf9000040, 0xf9400041, 0xf9400444,
                 0xf100a83f, 0x54000041, 0xd2800023, 0xd40000e1]
        code = struct.pack('<' + 'I' * len(words), *words)
        payload = bytearray(256)
        payload[:4] = b'NSO0'
        struct.pack_into('<I', payload, 60, 16)
        for index, content in enumerate((code, bytes(16), bytes(16))):
            struct.pack_into('<III', payload, 16 + 16 * index, len(payload), index * 4096, len(content))
            payload.extend(content)
        space = AddressSpace()
        space.load_nso(bytes(payload), 'main', FIRST_ADDRESS)
        space.relocate_relative(FIRST_ADDRESS, 'main', [(8200, 1027, 4)])
        buffers = [(ctypes.c_uint8 * entry['size']).from_buffer_copy(space.read(entry['base'], entry['size']))
                   for entry in space.mappings]
        mappings = (Region * len(buffers))(*[
            Region(entry['base'], entry['size'], buffer,
                   sum(value for key, value in (('r', 1), ('w', 2), ('x', 4)) if key in entry['permissions']))
            for entry, buffer in zip(space.mappings, buffers)])
        memory = Memory(mappings, len(mappings), 0)
        source = export(emit_machine(words, FIRST_ADDRESS), 'deku_machine')
        with native_library(self, source) as library:
            run = library.deku_machine
            run.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                            ctypes.POINTER(ctypes.c_uint64)]
            state, done = State(pc=FIRST_ADDRESS), ctypes.c_uint64()
            self.assertEqual(run(ctypes.byref(state), ctypes.byref(memory), 100, ctypes.byref(done)), 2)
            self.assertEqual((done.value, state.pc), (8, FIRST_ADDRESS + 32))
            self.assertEqual((state.x[0], state.x[1], state.x[3], state.x[4]), (42, 42, 1, FIRST_ADDRESS + 4))
            self.assertEqual(struct.unpack('<QQ', bytes(buffers[2])[:16]), (42, FIRST_ADDRESS + 4))

    def test_load_store_signed_width_and_addressing_against_oracle(self):
        words = cases()
        header = emit_machine([words[0]], BASE).split('int deku_machine', 1)[0]
        bodies = [emit_machine([word], BASE).split('int deku_machine', 1)[1] for word in words]
        source = header + '\n'.join(export('int memory_' + str(i) + body, 'memory_' + str(i))
                                    for i, body in enumerate(bodies))
        cpu, arm, registers = oracle()
        code_data = (ctypes.c_uint8 * 8192)()
        data = (ctypes.c_uint8 * 4096)()
        regions = (Region * 2)(Region(BASE - 4096, len(code_data), code_data, 1),
                               Region(DATA, len(data), data, 3))
        memory = Memory(regions, 2, 0)
        with native_library(self, source) as library:
            for index, word in enumerate(words):
                function = getattr(library, 'memory_' + str(index))
                function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]
                for seed in (0, 0x80, 0xff):
                    initial = bytes((seed + i) % 256 for i in range(len(data)))
                    data[:] = initial
                    code_data[:] = initial * 2
                    code_data[4096:4100] = struct.pack('<I', word)
                    cpu.mem_write(BASE - 4096, bytes(code_data))
                    cpu.mem_write(DATA, initial)
                    cpu.ctl_remove_cache(BASE, BASE + 4)
                    values = [0xfedcba9887654321] * 31
                    values[2] = DATA + 512
                    state = State((ctypes.c_uint64 * 31)(*values), DATA + 512, BASE, 0xa0000000)
                    load_state(cpu, arm, registers, state)
                    cpu.emu_start(BASE, BASE + 4, count=1)
                    done = ctypes.c_uint64()
                    self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 0)
                    self.assertEqual(done.value, 1)
                    assert_state(self, cpu, arm, registers, state, f'{word:08x}/{seed}')
                    self.assertEqual(bytes(data), bytes(cpu.mem_read(DATA, len(data))), hex(word))

    def test_faults_do_not_commit_partial_store_or_writeback(self):
        # STR X0,[X2],#8; LDR X0,[X2,#8]!; LDR XZR,[X2]
        words = [0xf8008440, 0xf8408c40, 0xf940005f]
        sources = [emit_machine([word], BASE + index * 4) for index, word in enumerate(words)]
        header = sources[0].split('int deku_machine', 1)[0]
        source = header + '\n'.join(export('int fault_' + str(i) + body.split('int deku_machine', 1)[1],
                                           'fault_' + str(i)) for i, body in enumerate(sources))
        data = (ctypes.c_uint8 * 8)(*b'abcdefgh')
        regions = (Region * 1)(Region(DATA, 8, data, 3))
        memory = Memory(regions, 1, 0)
        with native_library(self, source) as library:
            for index in range(3):
                function = getattr(library, 'fault_' + str(index))
                function.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Memory), ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]
                state = State(pc=BASE + index * 4)
                state.x[0], state.x[2] = 0x1234, DATA + 4
                before = bytes(state)
                done = ctypes.c_uint64(99)
                self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 3)
                self.assertEqual((done.value, bytes(state), bytes(data)), (0, before, b'abcdefgh'))
                self.assertGreaterEqual(memory.fault_address, DATA + 8)
            # XZR loads still perform a checked access; zero is not an elision.
            regions[0].permissions = 0
            state.pc = BASE + 8
            state.x[2] = DATA
            self.assertEqual(function(ctypes.byref(state), ctypes.byref(memory), 1, ctypes.byref(done)), 3)
            self.assertEqual(memory.fault_address, DATA)

    def test_reserved_memory_encodings_and_implicit_memory_are_rejected(self):
        for word in (0xf9800000, 0xb9c00000, 0x38800800, 0xf8400c00):
            with self.assertRaises(UnsupportedInstruction):
                decode(word)
        with self.assertRaises(UnsupportedInstruction):
            emit_c([0xf9400000])
