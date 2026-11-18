import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge import reports
from dekuforge.update_status import pending_result, load_result
from dekuforge.update_package import atomic_json


class UpdateStatusTests(unittest.TestCase):
    def test_outcome_is_visible_until_acknowledged_and_new_attempt_reappears(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsNone(pending_result(root))
            atomic_json(root/'local/update-result.json', {'success': True, 'release': 'v0.3.0-preview.2'})
            first = pending_result(root)
            self.assertTrue(first['success'])
            atomic_json(root/'local/update-result-seen.json', {'id': first['id']})
            self.assertIsNone(pending_result(root))
            atomic_json(root/'local/update-result.json', {'success': False, 'release': 'v0.3.0-preview.2', 'error': 'Failure'})
            self.assertFalse(pending_result(root)['success'])
            self.assertNotEqual(pending_result(root)['id'], first['id'])
            (root/'local/update-result.json').write_text('invalid JSON')
            self.assertIsNone(load_result(root))

    def test_failed_update_report_prioritizes_its_reviewed_worker_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root/'local/update-jobs'/('a'*32)
            job.mkdir(parents=True)
            atomic_json(job/'job.json', {'release': 'v0.3.0-preview.2'})
            (job/'worker.log').write_text('Update rolled back: synthetic failure\n')
            incident = {'kind': 'application_update', 'release': 'v0.3.0-preview.2', 'error': 'synthetic failure'}
            for identity in ('', 'a'*32, '../../outside'):
                with self.subTest(job=identity), patch('dekuforge.reports.hardware', return_value={'cpu': 'Test CPU'}):
                    context = reports.collect(root, incident={**incident, 'job': identity})
                self.assertEqual(context['logs'][0]['name'], 'worker.log')
                self.assertIn('synthetic failure', context['logs'][0]['text'])
                self.assertEqual(context['metadata']['incident']['release'], 'v0.3.0-preview.2')
            with patch('dekuforge.reports.hardware', return_value={}):
                ordinary = reports.collect(root)
            self.assertEqual(ordinary['logs'], [])
