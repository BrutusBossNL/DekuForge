import struct
import unittest

from dekuforge.gameplan import ADDRESS_LIMIT, FIRST_ADDRESS
from dekuforge.guest_memory import AddressSpace, GuestFault
from test_modules import executable


class GuestMemoryTests(unittest.TestCase):
    def test_permissions_bss_and_normalized_compressed_module(self):
        for compressed in (False, True):
            space = AddressSpace()
            metadata = space.load_nso(executable(compressed), 'main', FIRST_ADDRESS)
            self.assertEqual(metadata.base, FIRST_ADDRESS)
            self.assertEqual(space.fetch32(FIRST_ADDRESS), 0x01010101)
            self.assertEqual(space.read(FIRST_ADDRESS + 8192, 24), b'\x03' * 16 + b'\0' * 8)
            self.assertEqual([m['permissions'] for m in space.mappings], ['rx', 'r', 'rw'])
            space.write(FIRST_ADDRESS + 8208, b'12345678')
            self.assertEqual(space.read(FIRST_ADDRESS + 8208, 8), b'12345678')
            for address in (FIRST_ADDRESS, FIRST_ADDRESS + 4096):
                with self.assertRaises(GuestFault):
                    space.write(address, b'bad')
            with self.assertRaises(GuestFault):
                space.fetch32(FIRST_ADDRESS + 8192)
            with self.assertRaises(GuestFault):
                space.fetch32(FIRST_ADDRESS + 1)

    def test_partial_write_and_failed_module_mapping_are_atomic(self):
        space = AddressSpace(128)
        space.map(0x1000, 8, 'rw', b'abcdefgh')
        space.map(0x1008, 8, 'r', b'ijklmnop')
        with self.assertRaises(GuestFault):
            space.write(0x1004, b'12345678')
        self.assertEqual(space.read(0x1000, 16), b'abcdefghijklmnop')
        original = space.mappings
        for base in (0x1000, 1, -4096, ADDRESS_LIMIT):
            with self.assertRaises(GuestFault):
                space.load_nso(executable(), 'main', base)
            self.assertEqual(space.mappings, original)
        with self.assertRaises(GuestFault):
            space.map(0x1000, 129)
        with self.assertRaises(GuestFault):
            space.map(0x2000, 1, 'rwx')

    def test_relative_relocations_are_bounded_and_transactional(self):
        space = AddressSpace()
        space.load_nso(executable(), 'main', FIRST_ADDRESS)
        space.relocate_relative(FIRST_ADDRESS, 'main', [(8192, 1027, 4), (8200, 1027, -4)])
        before = space.read(FIRST_ADDRESS + 8192, 24)
        self.assertEqual(struct.unpack('<QQ', before[:16]), (FIRST_ADDRESS + 4, FIRST_ADDRESS - 4))
        bad_entries = [
            [(8208, 1027, 8), (0, 1027, 0)],  # first would fit, second targets code
            [(8208, 1027, 8), (8208, 1027, 9)],
            [(8208, 257, 8)], [(8208, (1 << 32) | 1027, 8)],
            [(8209, 1027, 8)], [(8208, 1027, ADDRESS_LIMIT)],
        ]
        for entries in bad_entries:
            with self.assertRaises(GuestFault):
                space.relocate_relative(FIRST_ADDRESS, 'main', entries)
            self.assertEqual(space.read(FIRST_ADDRESS + 8192, 24), before)
        with self.assertRaises(GuestFault):
            space.relocate_relative(FIRST_ADDRESS, 'other', [(8192, 1027, 0)])

    def test_ranges_cross_mapping_access_and_allocation_budget(self):
        space = AddressSpace(16)
        space.map(0x1000, 8, content=b'abcdefgh')
        space.map(0x1008, 8, content=b'ijklmnop')
        space.write(0x1006, b'1234')
        self.assertEqual(space.read(0x1000, 16), b'abcdef1234klmnop')
        for address, count in ((-1, 1), (ADDRESS_LIMIT, 0), (ADDRESS_LIMIT - 1, 2), (0, -1), (True, 1)):
            with self.assertRaises(GuestFault):
                space.read(address, count)
        with self.assertRaises(GuestFault):
            space.map(0x2000, 1)
        with self.assertRaises(GuestFault):
            space.read(0x1000, 17)
        self.assertEqual(space.read(0x1000, 0), b'')
