import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import MockModel
from tutor_comparison_service import TutorComparisons


class NavigationManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = TutorComparisons(MockModel(), self.temp.name)

    def tearDown(self):
        self.app.shutdown(); self.temp.cleanup()

    def test_packaged_practice_metadata_is_accepted_without_goals(self):
        path = Path(__file__).resolve().parents[2] / 'Assets/Project/Resources/Tutor/PracticeTaskSequence.json'
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest['purpose'], 'practice')
        for module in manifest['modules']:
            for task in module['tasks']:
                view = self.app.create({'request_id': task['task_code'], 'task_code': task['task_code'],
                    'domain': module['direction'], 'scenario': task['scenario'], 'require_preparation': True})
                self.assertEqual(view['task_code'], task['task_code'])
                self.assertIsNone(view['initial_query'])
                self.assertTrue(view['preparation_required'])
                self.assertNotIn(task['instructions'], json.dumps(view))

    def test_natural_scenario_is_metadata_not_a_model_request(self):
        view = self.app.create({'request_id': 'natural', 'task_code': 'PRACTICE-NATURAL',
                               'domain': 'natural_scenario', 'require_preparation': True})
        self.assertEqual(view['domain'], 'natural_scenario')
        self.assertIsNone(view['initial_query'])
        self.assertFalse(view['results_visible'])

    def test_instruction_field_cannot_enter_comparison_api(self):
        with self.assertRaises(APIError):
            self.app.create({'request_id': 'private', 'task_code': 'PRIVATE',
                             'instructions': 'PRIVATE_TARGET_DO_NOT_FORWARD'})
        self.assertEqual(len(self.app.tasks), 0)
        self.assertEqual(list(Path(self.temp.name).rglob('*.jsonl')), [])


if __name__ == '__main__': unittest.main()
