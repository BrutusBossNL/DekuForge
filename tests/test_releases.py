"""Release-channel separation without network access."""
import io
import json
import unittest
from unittest.mock import patch

from dekuforge.releases import INDEPENDENT_DESCRIPTOR, list_releases
from dekuforge.release_ui import displayed_releases, release_action


class ReleaseChannelTests(unittest.TestCase):
    def test_versions_are_sorted_numerically_and_notes_come_from_github(self):
        releases = [{'tag_name': name, 'body': 'Notes for '+name, 'prerelease': True,
                     'assets': [{'name': INDEPENDENT_DESCRIPTOR}]}
                    for name in ('v0.3.0-preview.2', 'v0.3.0-preview.10', 'v0.2.0')]
        with patch('dekuforge.releases.github_token', return_value=None), \
                patch('dekuforge.releases.urlopen', return_value=io.BytesIO(json.dumps(releases).encode())):
            result = list_releases(True)
        self.assertEqual([r['version'] for r in result], ['v0.3.0-preview.10', 'v0.3.0-preview.2', 'v0.2.0'])
        self.assertEqual(result[0]['notes'], 'Notes for v0.3.0-preview.10')

    def test_installed_version_is_visible_even_outside_current_channel(self):
        rows = displayed_releases([{'version':'v0.2.0','preview':False}], '0.3.0-preview.2')
        self.assertEqual([r['version'] for r in rows], ['v0.3.0-preview.2','v0.2.0'])
        self.assertEqual(release_action('v0.3.0-preview.10', '0.3.0-preview.2'), 'update')
        self.assertEqual(release_action('v0.2.0', '0.3.0-preview.2'), 'downgrade')
        self.assertEqual(release_action('v0.3.0-preview.2', '0.3.0-preview.2'), 'rebuild')

    def test_preview_is_excluded_from_stable_even_when_newer(self):
        releases = [
            {'tag_name': 'v0.3.0-preview.1', 'published_at': '2026-11-18', 'prerelease': True},
            {'tag_name': 'v0.2.0', 'published_at': '2026-11-17', 'prerelease': False},
            {'tag_name': 'v9.0.0', 'published_at': '2026-11-19', 'draft': True},
        ]
        for release in releases:
            release['assets'] = [{'name': INDEPENDENT_DESCRIPTOR}]
        releases.append({'tag_name': 'v9.0.1', 'assets': [{'name': 'DekuForge-release.json'}]})
        for preview, expected in ((False, ['v0.2.0']), (True, ['v0.3.0-preview.1', 'v0.2.0'])):
            with self.subTest(preview=preview), patch('dekuforge.releases.github_token', return_value=None), \
                    patch('dekuforge.releases.urlopen', return_value=io.BytesIO(json.dumps(releases).encode())):
                self.assertEqual([r['version'] for r in list_releases(preview)], expected)

    def test_experimental_switch_is_distinct_from_version_changes(self):
        preview = '0.4.0-preview.5'
        experimental = '0.4.0-experimental.10.1'
        self.assertEqual(release_action('v'+experimental, preview), 'switch_channel')
        self.assertEqual(release_action('v'+preview, experimental), 'switch_channel')
        self.assertEqual(release_action('v0.4.0-experimental.11.1', experimental), 'update')
        self.assertEqual(release_action('v0.4.0-experimental.9.1', experimental), 'downgrade')
        self.assertEqual(release_action('v'+experimental, experimental), 'rebuild')
        self.assertTrue(displayed_releases([], experimental)[0]['experimental'])
