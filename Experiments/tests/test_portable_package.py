"""Check the distributed package without StudyData, providers or browser state."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

EXPERIMENTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENTS / 'scripts'))
from build_review import embedded_data, walk_audio


class PortablePackageTests(unittest.TestCase):
    def test_all_manifest_assets_are_real_local_wavs(self):
        folder = EXPERIMENTS / 'runs/text-check-v4'
        manifest = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual(len(manifest['audio_assets']), 128)
        for asset in manifest['audio_assets']:
            path = Path(asset['path'])
            self.assertFalse(path.is_absolute())
            self.assertNotIn('..', path.parts)
            raw = (folder / path).read_bytes()
            self.assertEqual(raw[:4], b'RIFF')
            self.assertEqual(raw[8:12], b'WAVE')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), asset['sha256'])
            self.assertEqual(len(raw), asset['bytes'])

    def test_v2_and_v3_pages_keep_same_stimuli_and_relative_audio(self):
        folder = EXPERIMENTS / 'runs/text-check-v4'
        modern = embedded_data((folder / 'REVIEW_AND_QUESTIONNAIRE.html').read_text())
        legacy = embedded_data((folder / 'REVIEW_AND_QUESTIONNAIRE_v2.html').read_text())
        self.assertEqual(modern['questionnaire_version'], 'attribute-summary-feedback-v3')
        self.assertEqual(legacy['questionnaire_version'], 'attribute-summary-feedback-v2')
        self.assertEqual(modern['batch_id'], legacy['batch_id'])
        self.assertEqual([(t['task_code'], t['release_id']) for t in modern['tasks']],
                         [(t['task_code'], t['release_id']) for t in legacy['tasks']])
        self.assertEqual(set(walk_audio(modern)), set(walk_audio(legacy)))
        self.assertEqual(len(set(walk_audio(modern))), 128)
        for page in (modern, legacy):
            for audio in walk_audio(page):
                self.assertTrue(audio.startswith('audio/'))
                self.assertNotIn('://', audio)
                self.assertNotIn('..', Path(audio).parts)
            self.assertNotIn('/Users/', json.dumps(page))

    def test_manifest_public_file_hashes_and_original_page_hash(self):
        folder = EXPERIMENTS / 'runs/text-check-v4'
        manifest = json.loads((folder / 'manifest.json').read_text())
        for filename, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder / filename).read_bytes()).hexdigest(), digest)
        self.assertEqual(hashlib.sha256((folder / 'REVIEW_AND_QUESTIONNAIRE_v2.html').read_bytes()).hexdigest(),
                         manifest['source_v2_page_sha256'])
        self.assertFalse(manifest['participant_answers_prefilled'])

    def test_prepare_new_workbook_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'new-batch'
            args = [sys.executable, str(EXPERIMENTS / 'scripts/prepare_batch.py'), '--directory', str(destination)]
            first = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            raw = (destination / 'TASK_REQUESTS.md').read_bytes()
            self.assertEqual(raw.count(b'<!-- request:'), 32)
            second = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual((destination / 'TASK_REQUESTS.md').read_bytes(), raw)
            self.assertFalse((destination / 'batch.json').exists())


if __name__ == '__main__':
    unittest.main()
