import struct
import unittest

from dekuforge.mesh_stage import metadata, vulkan_stage


class MeshStageTests(unittest.TestCase):
    def fixture(self, stage=7, payload=256):
        control = bytearray(0xd8)
        code = bytearray(0x300)
        struct.pack_into("<II", control, 0, 0x98761234, 0xc9)
        struct.pack_into("<I", control, 0x38, 0x200)
        struct.pack_into("<II", control, 0x40, 0x300, 0x300)
        control[0x56] = stage
        struct.pack_into("<HH", control, 0x58, 32, payload)
        control[0x5f] = 3
        struct.pack_into("<HH", control, 0x60, 64, 126)
        code[0x35] = 0xf0
        return control, code

    def test_mesh_allocates_whole_primitive_blocks_and_position_lanes(self):
        ctl, code = self.fixture()
        info = metadata(ctl, code)
        self.assertEqual(info["vertex"], [("position", n) for n in range(4)])
        self.assertEqual(info["stage_memory"][3], 272 + 2 * 4 * 128)
        self.assertEqual(info["shared"] - info["stage_memory"][3], 4 + 128 * 3)

    def test_mesh_without_task_can_have_no_payload(self):
        ctl, code = self.fixture(payload=0)
        info = metadata(ctl, code)
        source = f"#version 450\nshared uint mem[{info['shared']//4}];\nvoid main() {{ return; }}"
        result = vulkan_stage(source, info)
        self.assertNotIn("taskPayloadSharedEXT", result)
        self.assertIn("df_first()+gl_WorkGroupID.x", result)
        self.assertIn("DfIndirect(df_draw.address).first", result)
        self.assertIn("SetMeshOutputsEXT", result)

    def test_task_hands_output_payload_and_count_to_mesh(self):
        ctl, code = self.fixture(stage=6)
        info = metadata(ctl, code)
        source = f"#version 450\nshared uint mem[{info['shared']//4}];\nvoid main() {{ return; }}"
        result = vulkan_stage(source, info)
        self.assertIn("EmitMeshTasksEXT(mem[77],1u,1u)", result)
        self.assertIn("df_payload.words[i]=mem[76u+i]", result)

    def test_payload_flags_do_not_change_size_and_header_fits(self):
        ctl, code = self.fixture(stage=6, payload=0)
        ctl[0x5a] = 0x80
        self.assertEqual(metadata(ctl, code)["payload"], 288)
        ctl[0x5b] = 12
        self.assertEqual(metadata(ctl, code)["payload"], 3104)
        ctl[0x56] = 7
        ctl[0x5e] = 1
        ctl[0x5a] = 0
        self.assertEqual(metadata(ctl, code)["payload"], 3104)
        ctl[0x5e] = 0
        ctl[0x5b] = 0
        ctl[0x5a] = 0x80
        self.assertEqual(metadata(ctl, code)["payload"], 0)

    def test_malformed_control_and_mismatched_shared_memory_fail(self):
        ctl, code = self.fixture()
        for short_ctl, short_code in ((ctl[:0x60], code), (ctl, code[:0x80])):
            with self.assertRaises(ValueError):
                metadata(short_ctl, short_code)
        struct.pack_into("<I", ctl, 0x64, 0x4000)
        ctl[0x68] = 0x80
        with self.assertRaises(ValueError):
            metadata(ctl, code)
        ctl[0x68] = 0
        with self.assertRaises(ValueError):
            vulkan_stage("#version 450\nshared uint wrong[1];\nvoid main() {}", metadata(ctl, code))
