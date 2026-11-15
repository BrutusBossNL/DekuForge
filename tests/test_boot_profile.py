import struct
import unittest

from dekuforge.boot_profile import module_boot_metadata


def module():
    header = bytearray(256)
    header[:4] = b"NSO0"
    image = bytearray(512)
    struct.pack_into("<I", image, 4, 32)
    image[32:36] = b"MOD0"
    struct.pack_into("<i", image, 36, 64 - 32)
    for index, pair in enumerate(((12, 128), (25, 256), (27, 24), (0, 0))):
        struct.pack_into("<QQ", image, 64 + 16 * index, *pair)
    for index, (offset, size) in enumerate(((0, 256), (256, 128), (384, 128))):
        struct.pack_into("<III", header, 16 + 16 * index, 256 + offset, offset, size)
    return header + image


class BootProfileTests(unittest.TestCase):
    def test_metadata_uses_array_size_including_empty_array(self):
        payload = module()
        self.assertEqual(module_boot_metadata(payload, "sdk")["constructor_count"], 3)
        struct.pack_into("<Q", payload, 256 + 104, 0)
        self.assertEqual(module_boot_metadata(payload, "sdk")["constructor_count"], 0)

    def test_rejects_invalid_dynamic_and_constructor_extents(self):
        for offset, value in ((4, 0xFFFFFFFF), (36, -100), (104, 7), (104, 4096), (72, 512)):
            payload = module()
            struct.pack_into("<i" if value < 0 else "<I", payload, 256 + offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                module_boot_metadata(payload, "sdk")

    def test_rejects_duplicate_boot_tags(self):
        payload = module()
        struct.pack_into("<Q", payload, 256 + 80, 12)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            module_boot_metadata(payload, "sdk")
