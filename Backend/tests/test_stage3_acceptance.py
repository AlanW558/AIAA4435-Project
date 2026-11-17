"""Combined sequence regression and live acceptance budget safety, all fixtures."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import DeepSeekModel, ModelError
from validate_stage3_acceptance import Acceptance, BoundedModel, fixture_model, load_environment


class Stage3AcceptanceTests(unittest.TestCase):
    def test_full_sequence_preserves_evidence_and_independent_baselines(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            output = Path(folder) / 'run'
            report = Acceptance(fixture_model(), output).run()
            self.assertTrue(report['passed'], report.get('error'))
            self.assertEqual(len(report['tasks']), 2)
            self.assertEqual(report['provider_attempts'], 0)
            self.assertEqual(len(list(output.glob('*-dialogue.jsonl'))), 2)
            first = json.loads((output / '05-submitted.json').read_text())
            self.assertEqual(first['lifecycle'], 'submitted')
            self.assertEqual(first['branches']['E']['result']['state']['settings']['jacket_color'], 'green')
            second = json.loads((output / '07-alternatives-aborted.json').read_text())
            self.assertEqual(second['lifecycle'], 'aborted')
            self.assertEqual(second['baseline']['settings']['jacket_color'], 'blue')

    def test_concurrent_live_budget_is_hard_and_no_fallback_or_retries(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'fixture-only', 'DEEPSEEK_MODEL': 'fixture-model', 'DEEPSEEK_FALLBACK_API_KEY': 'unused-fixture'}), redirect_stdout(io.StringIO()):
            model = BoundedModel(limit=3)
            self.assertEqual(model.max_attempts, 1)
            self.assertEqual(model.fallback_key, '')
            with patch.object(DeepSeekModel, '_call', return_value=({}, [{'status': 'fixture'}])) as provider:
                def invoke(_):
                    try: model._call('test', '', {}); return True
                    except ModelError: return False
                with ThreadPoolExecutor(max_workers=12) as pool: results = list(pool.map(invoke, range(24)))
            self.assertEqual(sum(results), 3)
            self.assertEqual(provider.call_count, 3)
            self.assertEqual(model.attempts, 3)

    def test_failed_generation_stops_and_preserves_failure_report(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            model = fixture_model()
            model.generate_tutor = lambda context: (_ for _ in ()).throw(ModelError('Explicit fixture failure'))
            output = Path(folder) / 'failure'
            report = Acceptance(model, output).run()
            self.assertFalse(report['passed'])
            self.assertIn('no automatic retry', report['error'])
            self.assertTrue((output / 'failure-state.json').exists())
            self.assertEqual(len(report['tasks']), 1)

    def test_environment_loader_does_not_execute_shell_or_overwrite_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'DEEPSEEK_MODEL': 'existing'}, clear=True):
            config = Path(folder) / '.env'
            marker = Path(folder) / 'must-not-exist'
            config.write_text('DEEPSEEK_MODEL=other\nDEEPSEEK_API_KEY="fixture-only"\nIGNORED=$(touch ' + str(marker) + ')\n')
            load_environment(config)
            self.assertEqual(os.environ['DEEPSEEK_MODEL'], 'existing')
            self.assertEqual(os.environ['DEEPSEEK_API_KEY'], 'fixture-only')
            self.assertNotIn('IGNORED', os.environ)
            self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
