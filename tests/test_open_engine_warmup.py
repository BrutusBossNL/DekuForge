import unittest

from dekuforge.open_engine_warmup import ready


class WarmupReadinessTests(unittest.TestCase):
    def test_startup_status_or_completion_file_alone_is_not_game_readiness(self):
        self.assertFalse(ready({'ok': True, 'frame': 0, 'renderer': 'none (built without wgpu)'}))
        self.assertFalse(ready({'ok': True, 'frame': 200, 'renderer': 'none'}))
        self.assertFalse(ready({'ok': False, 'frame': 200, 'renderer': 'GPU (Vulkan, native)'}))
        self.assertFalse(ready({'ok': True, 'frame': '200', 'renderer': 'GPU (Vulkan, native)'}))
        self.assertFalse(ready({'ok': True, 'frame': 200, 'replayed': 0, 'renderer': 'GPU (Vulkan, native)'}))
        self.assertTrue(ready({'ok': True, 'frame': 2, 'replayed': 2, 'renderer': 'GPU (Vulkan, native)'}))
