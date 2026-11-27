"""Acceptance validator tests use an isolated mock batch, never live API inputs."""
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'Backend'))
sys.path.insert(0, str(ROOT / 'Backend/tests'))
sys.path.insert(0, str(ROOT / 'Tools/TutorTextCheck'))
from batch import Batch
from report import generate as generate_report, collect
from workbook import generate, parse, replace_fields
from verify_release import verify, inspect_wav, blank_page_state
from unity_comparison_fixture_server import ComparisonFixture


def fixture_wav(silent=False):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(struct.pack('<100h', *([0] * 100 if silent else [600, -600] * 50)))
    return buffer.getvalue()


class FixtureTTS:
    def synthesize(self, text, settings): return {'audio': fixture_wav(), 'cache_hit': False}


class ReleaseQA(unittest.TestCase):
    def test_wav_pcm_is_decodable_and_non_silent(self):
        result = inspect_wav(fixture_wav())
        self.assertEqual(result['frames'], 100)
        self.assertEqual(result['sample_rate'], 24000)
        with self.assertRaisesRegex(ValueError, 'zero-valued'): inspect_wav(fixture_wav(silent=True))

    def test_complete_mock_batch_provenance_html_blanks_and_read_only_files(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=AssertionError('No provider calls in QA tests')):
            root = Path(folder); workbook = root / 'TASK_REQUESTS.md'; generate(workbook)
            fields = parse(workbook)
            workbook.write_text(replace_fields(workbook.read_text(), {(code, 'request'): 'Compare an easier explanation.' for code in fields}))
            batch = Batch(root, ComparisonFixture(), FixtureTTS())
            try:
                batch.process(workbook, limit=32, request_source='assistant_revised_user_authorized')
                replies = {}
                for code in fields:
                    questions = batch.questions(batch.view(batch.load(code)))
                    if questions: replies[(code, 'clarification')] = '\n'.join(c + ': Yes, use the first option.' for c in questions)
                workbook.write_text(replace_fields(workbook.read_text(), replies))
                batch.process(workbook, limit=32, request_source='assistant_revised_user_authorized', clarification_source='assistant_authored_user_authorized')
                batch.publish(workbook); generate_report(root)
            finally: batch.close()
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            result = verify(root)
            self.assertEqual(result['strategy_audio_files'], 128)
            self.assertEqual(result['blank_questionnaire']['total_required_responses'], 84)
            self.assertEqual(result['request_provenance'], {'assistant_revised_user_authorized': 32})
            self.assertEqual(result['batch_writes'], 0)
            self.assertEqual(before, {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()})
            if os.environ.get('TUTOR_QA_BROWSER_FIXTURE') == '1':
                browser = subprocess.run(['node', str(ROOT / 'Tools/TutorTextCheck/verify_browser.cjs'), str(root)],
                                         text=True, capture_output=True, timeout=120)
                self.assertEqual(browser.returncode, 0, browser.stderr)
                browser_result = json.loads(browser.stdout)
                self.assertEqual(browser_result['decoded_audio'], 128)
                self.assertEqual(browser_result['required_blank_answers'], 84)
            html = root / 'REVIEW_AND_QUESTIONNAIRE.html'; original = html.read_text()
            html.write_text(original.replace('"audio_count": 128', '"audio_count": 127'))
            with self.assertRaisesRegex(ValueError, 'HTML dataset is stale'): verify(root)
            html.write_text(original)
            altered = original.replace("status:'unanswered',value:null", "status:'answered',value:4")
            with self.assertRaisesRegex(ValueError, 'initially empty'): blank_page_state(altered, collect(root))


if __name__ == '__main__': unittest.main()
