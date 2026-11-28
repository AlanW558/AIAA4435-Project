from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('appearance_aggregate', PACKAGE / 'scripts/aggregate_results.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.example = module.load(PACKAGE / 'results/participant_001.json')
        self.evidence = module.load(PACKAGE / 'materials/review_evidence.json')['evidence']
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def save(self, record, name):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(record))
        return path

    def test_missing_ratings_and_multiselect_use_correct_denominators(self):
        records = [deepcopy(self.example) for _ in range(3)]
        for i, record in enumerate(records):
            record['participant_id'] = 'TEST' + str(i)
        records[0]['conditions']['E']['answers']['A0'] = {'status': 'answered', 'value': 1}
        records[1]['conditions']['E']['answers']['A0'] = {'status': 'answered', 'value': 7}
        records[2]['conditions']['E']['answers']['A0'] = {'status': 'unable_to_judge', 'value': None}
        records[0]['preference'] = {'status': 'answered', 'value': ['N', 'S']}
        records[1]['preference'] = {'status': 'answered', 'value': ['S']}
        records[2]['preference'] = {'status': 'no_preference', 'value': None}
        paths = [self.save(r, f'{i}.json') for i, r in enumerate(records)]
        result = module.aggregate(paths, evidence=self.evidence)
        item = result['ratings_by_condition_and_item']['E']['A0']
        self.assertEqual((item['n_total'], item['n_numeric'], item['n_unable_to_judge']), (3, 2, 1))
        self.assertEqual((item['mean'], item['median']), (4, 4))
        self.assertAlmostEqual(item['sample_sd'], math.sqrt(18))
        self.assertEqual(item['distribution'], {'1': 1, '2': 0, '3': 0, '4': 0, '5': 0, '6': 0, '7': 1})
        pref = result['preference_summary']
        self.assertEqual(pref['selection_counts'], {'E': 0, 'A': 0, 'N': 1, 'S': 2})
        self.assertEqual(pref['selection_proportions_of_all_participants']['S'], 2/3)
        self.assertEqual((pref['participant_denominator'], pref['no_preference_count']), (3, 1))
        self.assertEqual((result['numeric_rating_count'], result['unable_to_judge_count']), (59, 1))

    def test_all_missing_is_not_zero_and_single_value_has_no_sd(self):
        self.example['conditions']['S']['answers']['A4'] = {'status': 'unable_to_judge', 'value': None}
        result = module.aggregate([self.save(self.example, 'one.json')], evidence=self.evidence)
        missing = result['ratings_by_condition_and_item']['S']['A4']
        self.assertIsNone(missing['mean'])
        self.assertIsNone(missing['median'])
        self.assertIsNone(missing['sample_sd'])
        self.assertIsNone(result['ratings_by_condition_and_item']['E']['A0']['sample_sd'])

    def test_duplicate_id_including_case_variant_is_rejected(self):
        one = self.save(self.example, 'one.json')
        other = deepcopy(self.example)
        other['participant_id'] = other['participant_id'].lower()
        with self.assertRaisesRegex(ValueError, 'Duplicate participant'):
            module.aggregate([one, self.save(other, 'two.json')], evidence=self.evidence)

    def test_draft_or_wrong_questionnaire_rejected(self):
        for key, value in [('status', 'draft'), ('questionnaire_version', 'old-version')]:
            with self.subTest(key=key):
                changed = deepcopy(self.example)
                changed[key] = value
                with self.assertRaises(ValueError):
                    module.aggregate([self.save(changed, 'bad.json')], evidence=self.evidence)

    def test_mixed_release_and_changed_request_source_rejected(self):
        for key, value in [('evidence', {**self.evidence, 'batch_id': 'different'}),
                           ('request_source', 'user_supplied_text')]:
            with self.subTest(key=key):
                changed = deepcopy(self.example)
                changed[key] = value
                with self.assertRaises(ValueError):
                    module.aggregate([self.save(changed, 'bad.json')], evidence=self.evidence)

    def test_incomplete_invalid_ratings_and_preference_rejected(self):
        for value in (True, 0, 8, 3.5, '5', None):
            with self.subTest(value=value):
                record = deepcopy(self.example)
                record['conditions']['E']['answers']['A0']['value'] = value
                with self.assertRaises(ValueError):
                    module.validate(record, self.evidence)
        record = deepcopy(self.example)
        del record['conditions']['A']['answers']['A3']
        with self.assertRaises(ValueError): module.validate(record, self.evidence)
        for preference in ({'status': 'unanswered', 'value': None},
                           {'status': 'no_preference', 'value': ['S']},
                           {'status': 'answered', 'value': ['S', 'S']}):
            record = deepcopy(self.example)
            record['preference'] = preference
            with self.assertRaises(ValueError): module.validate(record, self.evidence)

    def test_raw_source_checksum_is_enforced(self):
        path = self.save(self.example, 'one.json')
        manifest = {'participants': [{'stored_filename': 'one.json', 'participant_id': 'P001',
                    'sha256': module.sha(path.read_bytes()), 'original_download_filename': 'download.json'}]}
        result = module.aggregate([path], evidence=self.evidence, source_manifest=manifest)
        self.assertEqual(result['source_files'][0]['original_download_filename'], 'download.json')
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            module.aggregate([path], evidence=self.evidence, source_manifest=manifest)

    def test_real_four_exports_are_complete_and_deterministic(self):
        paths = sorted((PACKAGE / 'results').glob('participant_*.json'))
        manifest = module.load(PACKAGE / 'source_manifest.json')
        first = module.aggregate(paths, evidence=self.evidence, source_manifest=manifest)
        second = module.aggregate(list(reversed(paths)), evidence=self.evidence, source_manifest=manifest)
        self.assertEqual(first, second)
        self.assertEqual((first['participant_count'], first['rating_row_count'], first['numeric_rating_count']), (4, 80, 80))
        self.assertEqual(first['preference_summary']['selection_counts'], {'E': 0, 'A': 0, 'N': 2, 'S': 4})
        self.assertEqual(first['participant_records'][0], self.example)


if __name__ == '__main__':
    unittest.main()
