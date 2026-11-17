"""Release-channel separation without network access."""
import io
import json
import unittest
from unittest.mock import patch

from dekuforge.releases import list_releases


class ReleaseChannelTests(unittest.TestCase):
    def test_preview_is_excluded_from_stable_even_when_newer(self):
        releases = [
            {'tag_name': 'v0.3.0-preview.1', 'published_at': '2026-11-18', 'prerelease': True},
            {'tag_name': 'v0.2.0', 'published_at': '2026-11-17', 'prerelease': False},
            {'tag_name': 'v9.0.0', 'published_at': '2026-11-19', 'draft': True},
        ]
        for preview, expected in ((False, ['v0.2.0']), (True, ['v0.3.0-preview.1', 'v0.2.0'])):
            with self.subTest(preview=preview), patch('dekuforge.releases.github_token', return_value=None), \
                    patch('dekuforge.releases.urlopen', return_value=io.BytesIO(json.dumps(releases).encode())):
                self.assertEqual([r['version'] for r in list_releases(preview)], expected)
