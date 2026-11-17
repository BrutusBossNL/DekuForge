import unittest
import tempfile
from pathlib import Path
from tools.package_launcher import included
from tools.check_source import forbidden
from dekuforge import COMPONENTS, __version__
from dekuforge.runtime_layer import gpu_input_signature


class DistributionTests(unittest.TestCase):
    def test_only_declared_launcher_sources_and_artwork_can_ship(self):
        for name in ("local/settings.json", "build/world.c", "python/python.exe",
                     "pydeps/zbic.pyd", "romfs/textures.png", "assets/branding/dump.nup",
                     "engine/generated/main.c", "tools/seed-programs.bin",
                     "dekuforge/__pycache__/ui.pyc", "assets/branding/save.png"):
            self.assertFalse(included(name), name)
        for name in ("run_launcher.py", "tools/bootstrap_runtime.ps1",
                     "dekuforge/components.json", "assets/branding/logo.png",
                     "engine_overrides/dekuforge_0110/cheat_manager.patch"):
            self.assertTrue(included(name), name)

    def test_renamed_game_inputs_are_refused_even_in_an_allowed_source_path(self):
        for magic in (b"NSO0", b"NUP\x01", b"PFS0", b"MZ", b"\x7fELF"):
            self.assertTrue(forbidden("tools/unexpected.py", magic))

    def test_launcher_engine_and_buildkit_versions_have_separate_roles(self):
        self.assertEqual(__version__, COMPONENTS["launcher"]["version"])
        self.assertEqual(COMPONENTS["engine"]["backend"], "independent")
        self.assertNotIn("base_version", COMPONENTS["engine"])
        self.assertIsNone(COMPONENTS["python"]["url"])
        self.assertNotEqual(COMPONENTS["launcher"]["version"], COMPONENTS["engine"]["version"])
        self.assertIn("version", COMPONENTS["buildkit"])

    def test_shader_carry_rejects_renderer_changes_but_accepts_menu_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            renderer = source / "runtime/vk_mesh.c"
            menu = source / "runtime/ui/menu.cpp"
            menu.parent.mkdir(parents=True)
            renderer.write_text("renderer v1", encoding="utf-8")
            menu.write_text("menu v1", encoding="utf-8")
            names = ["runtime/vk_mesh.c", "runtime/ui/menu.cpp"]
            original = gpu_input_signature(source, names)
            menu.write_text("new menu", encoding="utf-8")
            self.assertEqual(original, gpu_input_signature(source, names))
            renderer.write_text("renderer v2", encoding="utf-8")
            self.assertNotEqual(original, gpu_input_signature(source, names))
