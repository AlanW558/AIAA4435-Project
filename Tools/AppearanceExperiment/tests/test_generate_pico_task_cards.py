"""Frozen task material generation tests; fixture PNGs are not study evidence."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_pico_task_cards as cards


def fixture_png():
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    w, h = cards.SETTINGS['width'], cards.SETTINGS['height']
    header = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff' * w * 4) * h)) + chunk(b'IEND', b'')


class TaskCardTests(unittest.TestCase):
    def setUp(self):
        self.tasks = cards.load_json(cards.SOURCE)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / 'output'
        self.source = Path(self.tmp.name) / 'tasks_private.json'
        self.source.write_text(json.dumps(self.tasks, ensure_ascii=False))
        self.avatar = Path(self.tmp.name) / 'Avatar.cs'
        self.avatar.write_text('// mock avatar source, not rendered')
        self.renderer = Path(self.tmp.name) / 'Renderer.cs'
        self.renderer.write_text('// mock renderer source, not rendered')
        self.sources = {'source': self.source, 'avatar_source': self.avatar, 'renderer_source': self.renderer}

    def prepare(self):
        return cards.prepare_bundle(self.output, **self.sources)

    def fake_receipt(self):
        manifest = cards.load_json(self.output / 'render-jobs.json')
        raw = fixture_png()
        entries = []
        for job in manifest['jobs']:
            (self.output / job['image']).write_bytes(raw)
            entries.append({'id': job['id'], 'image': job['image'], 'sha256': cards.digest_bytes(raw), 'observed': job['state']})
        receipt = {'schema_version': 'appearance-task-card-render-v1',
                   'manifest_sha256': cards.digest_bytes((self.output / 'render-jobs.json').read_bytes()),
                   'unity_version': 'MOCK_NO_UNITY_EXECUTED', 'render_mode': 'TEST_ONLY', 'images': entries}
        cards.write_json(self.output / 'render-receipt.json', receipt)
        return receipt

    def test_frozen_sixteen_tasks_include_all_twenty_targets(self):
        before = self.source.read_bytes()
        result = self.prepare()
        manifest = cards.load_json(result['manifest'])
        self.assertEqual((result['cards'], result['render_jobs']), (16, 36))
        self.assertEqual({c['task_id'] for c in manifest['cards']}, cards.TASK_IDS)
        self.assertEqual(sum(len(c['targets']) for c in manifest['cards']), 20)
        for card in manifest['cards']:
            original = next(t for t in self.tasks if t['task_id'] == card['task_id'])
            for field, allowed in original['evaluator_only']['allowed_values'].items():
                self.assertEqual({t['state'][field] for t in card['targets']}, set(allowed))
            for target in card['targets']:
                for field in original['evaluator_only']['preserve_fields']:
                    self.assertEqual(target['state'][field], card['initial']['state'][field])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(manifest['source_sha256'], cards.digest_bytes(before))
        self.assertEqual(manifest['render_settings'], cards.SETTINGS)

    def test_multiple_allowed_fields_expand_cartesian_product(self):
        task = copy.deepcopy(self.tasks[0])
        task['evaluator_only']['allowed_values'] = {'jacket_color': ['gray', 'purple'], 'accessory': ['none', 'glasses']}
        task['evaluator_only']['preserve_fields'] = ['scale']
        target = cards.expand_task(task)
        self.assertEqual({(s['state']['jacket_color'], s['state']['accessory']) for s in target['targets']},
                         {('gray', 'none'), ('gray', 'glasses'), ('purple', 'none'), ('purple', 'glasses')})

    def test_duplicate_missing_ids_and_undefined_preservation_rejected(self):
        broken = [self.tasks[:-1], [self.tasks[0]] * 16]
        for value in broken:
            self.source.write_text(json.dumps(value))
            with self.assertRaises(cards.MaterialError):
                self.prepare()
        task = copy.deepcopy(self.tasks[0])
        task['evaluator_only']['preserve_fields'] = ['scale']
        with self.assertRaises(cards.MaterialError):
            cards.expand_task(task)

    def test_invalid_or_duplicate_target_values_rejected(self):
        for values in ([], ['invisible'], ['blue', 'blue'], [False], [None], [['blue']], [{'bad': 'blue'}]):
            task = copy.deepcopy(self.tasks[0])
            task['evaluator_only']['allowed_values']['jacket_color'] = values
            with self.subTest(values=values), self.assertRaises(cards.MaterialError):
                cards.expand_task(task)
        task = copy.deepcopy(self.tasks[4])
        task['evaluator_only']['allowed_values']['scale'] = [True]
        with self.assertRaises(cards.MaterialError):
            cards.expand_task(task)

    def test_scale_domain_matches_runtime_grid_and_float32_tolerance(self):
        base = {'jacket_color': 'gray', 'accessory': 'hat'}
        for scale in (.85, .90, .95, 1, 1.05, 1.10, 1.15):
            with self.subTest(scale=scale):
                self.assertEqual(cards.check_state(dict(base, scale=scale))['scale'], scale)
        self.assertEqual(cards.check_state(dict(base, scale=1.0499999523162842))['scale'], 1.05)
        for scale in (.80, 1.20, .849, 1.151, .875, .97, 1.051, True, float('nan'), float('inf')):
            with self.subTest(scale=scale), self.assertRaises(cards.MaterialError):
                cards.check_state(dict(base, scale=scale))
        task = copy.deepcopy(self.tasks[0])
        task['model_visible']['state']['scale'] = .80
        with self.assertRaises(cards.MaterialError):
            cards.expand_task(task)
        task = copy.deepcopy(self.tasks[4])
        task['evaluator_only']['allowed_values']['scale'] = [.875]
        with self.assertRaises(cards.MaterialError):
            cards.expand_task(task)

    def test_publish_requires_receipt_and_all_images(self):
        self.prepare()
        with self.assertRaises(cards.MaterialError):
            cards.publish_bundle(self.output, **self.sources)
        self.assertFalse((self.output / 'index.html').exists())
        self.fake_receipt()
        next((self.output / 'images').iterdir()).unlink()
        with self.assertRaises(OSError):
            cards.publish_bundle(self.output, **self.sources)
        self.assertFalse((self.output / 'index.html').exists())

    def test_publish_self_contained_cards_and_source_hash_sidecar(self):
        self.prepare()
        self.fake_receipt()
        result = cards.publish_bundle(self.output, **self.sources)
        self.assertEqual((result['cards'], result['images']), (16, 36))
        card = (self.output / 'A_T2.html').read_text()
        self.assertEqual(card.count('data:image/png;base64,'), 3)
        self.assertIn('1.05', card)
        self.assertIn('1.10', card)
        for marker in ('A_T2', 'task_set', 'request_class', '条件', '轮次'):
            self.assertNotIn(marker, card)
        self.assertIn('width:52mm;height:69.333mm', card)
        sidecar = cards.load_json(self.output / 'source-hashes.json')
        self.assertEqual(sidecar['files_sha256']['A_T2.html'], cards.digest_bytes(card.encode()))
        self.assertIn('A_T2', (self.output / 'index.html').read_text())

    def test_html_escapes_private_goal_text(self):
        card = cards.expand_task(self.tasks[0])
        card['goal_text'] = '<script>alert("x")</script>'
        images = {item['image']: b'test' for item in [card['initial'], *card['targets']]}
        page = cards.card_html(card, images)
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_source_or_avatar_drift_requires_new_render(self):
        self.prepare()
        self.fake_receipt()
        for path in (self.source, self.avatar, self.renderer):
            before = path.read_bytes()
            path.write_bytes(before + b'\n')
            with self.subTest(path=path), self.assertRaises(cards.MaterialError):
                cards.publish_bundle(self.output, **self.sources)
            path.write_bytes(before)

    def test_receipt_rejects_wrong_state_hash_duplicate_or_manifest(self):
        self.prepare()
        original = self.fake_receipt()
        variations = []
        altered = copy.deepcopy(original); altered['images'][0]['observed']['scale'] = 1.2; variations.append(altered)
        altered = copy.deepcopy(original); altered['images'][0]['sha256'] = '0' * 64; variations.append(altered)
        altered = copy.deepcopy(original); altered['images'][0] = altered['images'][1]; variations.append(altered)
        altered = copy.deepcopy(original); altered['manifest_sha256'] = '0' * 64; variations.append(altered)
        for receipt in variations:
            cards.write_json(self.output / 'render-receipt.json', receipt)
            with self.assertRaises(cards.MaterialError):
                cards.publish_bundle(self.output, **self.sources)
            self.assertFalse((self.output / 'index.html').exists())

    def test_prepare_invalidates_old_receipt_and_rejects_symlink_escape(self):
        self.prepare()
        self.fake_receipt()
        cards.publish_bundle(self.output, **self.sources)
        self.assertTrue((self.output / 'index.html').exists())
        self.prepare()
        for name in ('render-receipt.json', 'index.html', 'source-hashes.json', 'A_T1.html'):
            self.assertFalse((self.output / name).exists())
        with self.assertRaises(cards.MaterialError):
            cards.safe_file(self.output, '../escape.png')
        (self.output / 'elsewhere').symlink_to(Path(self.tmp.name), target_is_directory=True)
        with self.assertRaises(cards.MaterialError):
            cards.safe_file(self.output, 'elsewhere/escape.png')

    def test_prepare_refuses_manifest_link_into_frozen_sources(self):
        self.output.mkdir()
        before = self.source.read_bytes()
        (self.output / 'render-jobs.json').symlink_to(self.source)
        with self.assertRaises(cards.MaterialError):
            self.prepare()
        self.assertEqual(self.source.read_bytes(), before)

    def test_png_signature_checksum_size_and_truncation_fail_closed(self):
        path = Path(self.tmp.name) / 'image.png'
        valid = fixture_png()
        for raw in (b'not png', valid[:-5], valid[:40] + b'x' + valid[41:], valid + b'extra'):
            path.write_bytes(raw)
            with self.subTest(size=len(raw)), self.assertRaises(cards.MaterialError):
                cards.png_bytes(path)

    def test_cli_rejects_output_in_apk_assets_without_touching_them(self):
        with patch('sys.stderr'), patch.object(cards, 'prepare_bundle') as prepare:
            self.assertEqual(cards.main(['prepare', '--output', str(cards.ROOT / 'Assets/StreamingAssets')]), 1)
        prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
