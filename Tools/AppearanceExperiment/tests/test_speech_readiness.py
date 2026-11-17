import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'check_speech_readiness.py'
spec = importlib.util.spec_from_file_location('speech_readiness', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadinessTests(unittest.TestCase):
    def test_valid_shape_does_not_claim_provider_access(self):
        report = module.inspect({'QWEN_API_KEY': 'private-test-value',
            'QWEN_BASE_URL': 'https://workspace.cn-beijing.maas.aliyuncs.com'})
        self.assertTrue(report['configuration_ready'])
        self.assertFalse(report['provider_access_verified'])
        self.assertEqual(report['network_calls'], 0)
        self.assertNotIn('private-test-value', json.dumps(report))

    def test_missing_plan_and_incompatible_profiles_are_not_ready(self):
        base = {'QWEN_API_KEY': 'private-test-value',
                'QWEN_BASE_URL': 'https://workspace.cn-beijing.maas.aliyuncs.com'}
        for values in ({}, {**base, 'QWEN_API_KEY': 'sk-sp-private'},
                {**base, 'QWEN_BASE_URL': 'https://token-plan.cn-beijing.maas.aliyuncs.com'},
                {**base, 'QWEN_BASE_URL': 'https://untrusted.example'},
                {**base, 'QWEN_TTS_MODEL': 'unreviewed'},
                {**base, 'QWEN_TIMEOUT_SECONDS': 'nan'}):
            with self.subTest(values=list(values)):
                self.assertFalse(module.inspect(values)['configuration_ready'])

    def test_matching_plan_configuration_reports_scope_separately(self):
        report = module.inspect({'QWEN_API_KEY': 'sk-sp-private',
            'QWEN_BASE_URL': 'https://token-plan.cn-beijing.maas.aliyuncs.com'})
        self.assertTrue(report['configuration_ready'])
        self.assertFalse(report['provider_access_verified'])
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['warnings'],
            ['token_plan_provider_scope_restricted_to_interactive_ai_tools'])
        self.assertNotIn('sk-sp-private', json.dumps(report))

    def test_file_read_is_literal_and_does_not_modify_or_expose_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private.env'
            content = "export QWEN_API_KEY='test-secret'\nQWEN_BASE_URL='https://workspace.cn-beijing.maas.aliyuncs.com' # endpoint\n"
            path.write_text(content)
            output = io.StringIO()
            with patch.dict(module.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(module.main(['--env-file', str(path)]), 0)
            self.assertNotIn('test-secret', output.getvalue())
            self.assertEqual(path.read_text(), content)

    def test_shell_expansion_and_malformed_secret_fail_without_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private.env'
            for value in ('$(echo test-secret)', '`echo test-secret`', "'test-secret"):
                path.write_text('QWEN_API_KEY=' + value)
                output = io.StringIO()
                with patch.dict(module.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
                    self.assertEqual(module.main(['--env-file', str(path)]), 1)
                self.assertNotIn('test-secret', output.getvalue())
                self.assertIn('literal_assignments_required', output.getvalue())

    def test_missing_file_reports_sanitized_error(self):
        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with patch.dict(module.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(module.main(['--env-file', str(Path(folder) / 'absent')]), 1)
            self.assertIn('configuration_file_unreadable', output.getvalue())


if __name__ == '__main__':
    unittest.main()
