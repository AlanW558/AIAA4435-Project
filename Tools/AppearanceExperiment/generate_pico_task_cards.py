#!/usr/bin/env python3
"""Prepare editor-only render jobs, then publish genuine rendered offline cards.

Private targets stay outside Assets and APK inputs. This tool never runs Unity,
contacts a model/backend, or generates participant observations.
"""
import argparse
import base64
import hashlib
import html
import itertools
import json
import math
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Docs/AppearanceExperiment/Study/materials/tasks_private.json'
AVATAR_SOURCE = ROOT / 'Assets/Project/Scripts/AppearanceExperiment/AppearanceAvatar.cs'
RENDERER_SOURCE = ROOT / 'Assets/Editor/AppearanceTaskCards.cs'
DEFAULT_OUTPUT = ROOT / 'StudyData/pico/materials'
TASK_IDS = {f'{group}_T{number}' for group in 'ABCD' for number in range(1, 5)}
FIELDS = ('jacket_color', 'accessory', 'scale')
COLORS = {'blue': '蓝色', 'orange': '橙色', 'green': '绿色', 'gray': '灰色', 'red': '红色', 'purple': '紫色'}
ACCESSORIES = {'none': '无配饰', 'hat': '帽子', 'glasses': '眼镜'}
SETTINGS = {'width': 768, 'height': 1024, 'orthographic_size': 1.45,
            'camera_position': [0.0, 1.25, -5.0], 'camera_target': [0.0, 1.25, 0.0]}


class MaterialError(ValueError):
    pass


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise MaterialError('Duplicate JSON key.')
            result[key] = value
        return result
    def constant(_):
        raise MaterialError('Non-finite JSON number.')
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, ValueError) as exc:
        raise MaterialError('Cannot read valid materials JSON: ' + Path(path).name) from exc


def check_state(state):
    if not isinstance(state, dict):
        raise MaterialError('Task appearance must be an object.')
    if (not isinstance(state.get('jacket_color'), str) or state['jacket_color'] not in COLORS
            or not isinstance(state.get('accessory'), str) or state['accessory'] not in ACCESSORIES):
        raise MaterialError('Task appearance has an unknown color or accessory.')
    scale = state.get('scale')
    if type(scale) not in (int, float) or not math.isfinite(scale):
        raise MaterialError('Task scale must be finite and on the 0.85–1.15 grid with 0.05 increments.')
    nearest = round(scale * 20) / 20
    if not .85 <= nearest <= 1.15 or abs(scale - nearest) > 1e-5:
        raise MaterialError('Task scale must be on the 0.85–1.15 grid with 0.05 increments.')
    return {'revision': 0, 'jacket_color': state['jacket_color'], 'accessory': state['accessory'],
            'scale': round(nearest, 2)}


def expand_task(task):
    """Use every allowed combination; unspecified fields must be preserved."""
    if not isinstance(task, dict) or task.get('task_id') not in TASK_IDS:
        raise MaterialError('Expected a frozen task ID.')
    try:
        initial = check_state(task['model_visible']['state'])
        private = task['evaluator_only']
        allowed = private['allowed_values']
        preserved = private['preserve_fields']
        goal = private['participant_goal_text']
    except (KeyError, TypeError) as exc:
        raise MaterialError('Task is missing private target or initial appearance.') from exc
    if (not isinstance(allowed, dict) or not allowed or set(allowed) - set(FIELDS)
            or not isinstance(preserved, list) or any(not isinstance(f, str) for f in preserved)
            or set(allowed) & set(preserved) or set(allowed) | set(preserved) != set(FIELDS)
            or len(set(preserved)) != len(preserved)):
        raise MaterialError('Allowed and preserved fields must partition the appearance fields.')
    if not isinstance(goal, str) or not goal.strip():
        raise MaterialError('Task needs offline participant goal text.')
    options = []
    for field in FIELDS:
        values = allowed.get(field, [initial[field]])
        if not isinstance(values, list) or not values or len(values) > 10:
            raise MaterialError('Each allowed field requires a bounded nonempty value list.')
        if len({json.dumps(v, sort_keys=True) for v in values}) != len(values):
            raise MaterialError('Duplicate allowed target value.')
        options.append(values)
    targets = [check_state(dict(zip(FIELDS, combination))) for combination in itertools.product(*options)]
    if len(targets) > 32:
        raise MaterialError('Too many target combinations for one offline card.')
    task_id = task['task_id']
    return {'task_id': task_id, 'goal_text': goal,
            'initial': {'image': f'images/{task_id}_initial.png', 'state': initial},
            'targets': [{'image': f'images/{task_id}_target_{i:02d}.png', 'state': state}
                        for i, state in enumerate(targets, 1)]}


def build_manifest(source=SOURCE, avatar_source=AVATAR_SOURCE, renderer_source=RENDERER_SOURCE):
    tasks = load_json(source)
    if not isinstance(tasks, list) or len(tasks) != 16:
        raise MaterialError('Expected exactly 16 frozen tasks.')
    cards = [expand_task(task) for task in tasks]
    if {card['task_id'] for card in cards} != TASK_IDS:
        raise MaterialError('Frozen task IDs must appear exactly once.')
    jobs = []
    for card in cards:
        for image in [card['initial'], *card['targets']]:
            jobs.append({'id': Path(image['image']).stem, **image})
    return {'schema_version': 'appearance-task-card-jobs-v1',
            'purpose': 'researcher_offline_materials_not_participant_data',
            'source_sha256': digest_bytes(Path(source).read_bytes()),
            'avatar_source_sha256': digest_bytes(Path(avatar_source).read_bytes()),
            'renderer_source_sha256': digest_bytes(Path(renderer_source).read_bytes()),
            'render_settings': SETTINGS, 'cards': cards, 'jobs': jobs}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def prepare_bundle(output, source=SOURCE, avatar_source=AVATAR_SOURCE, renderer_source=RENDERER_SOURCE):
    manifest = build_manifest(source, avatar_source, renderer_source)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'images').mkdir(exist_ok=True)
    safe_file(output, 'images/placeholder.png')  # Refuse an escaping image-directory symlink.
    write_json(safe_file(output, 'render-jobs.json'), manifest)
    # Invalidate old publications as well as their receipt before another render.
    for name in ['render-receipt.json', 'index.html', 'source-hashes.json',
                 *(task_id + '.html' for task_id in TASK_IDS)]:
        safe_file(output, name).unlink(missing_ok=True)
    return {'manifest': str(output / 'render-jobs.json'), 'cards': len(manifest['cards']),
            'render_jobs': len(manifest['jobs']), 'state': 'awaiting_unity_render'}


def safe_file(output, relative):
    path = (Path(output) / relative).resolve()
    if Path(output).resolve() not in path.parents:
        raise MaterialError('Material file path escapes the output folder.')
    return path


def png_bytes(path):
    """Validate PNG signature, dimensions and complete chunks before embedding."""
    raw = Path(path).read_bytes()
    if len(raw) < 45 or raw[:8] != b'\x89PNG\r\n\x1a\n':
        raise MaterialError('Expected a real rendered PNG: ' + Path(path).name)
    offset, saw_header, saw_data, saw_end = 8, False, False, False
    while offset + 12 <= len(raw):
        size = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(raw) or saw_end:
            raise MaterialError('Truncated or trailing PNG data.')
        payload = raw[offset + 8:offset + 8 + size]
        crc = struct.unpack('>I', raw[offset + 8 + size:end])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise MaterialError('PNG checksum mismatch.')
        if not saw_header:
            if kind != b'IHDR' or size != 13:
                raise MaterialError('Missing PNG header.')
            width, height = struct.unpack('>II', payload[:8])
            if (width, height) != (SETTINGS['width'], SETTINGS['height']):
                raise MaterialError('PNG dimensions do not match the fixed camera output.')
            saw_header = True
        if kind == b'IDAT':
            saw_data = True
        if kind == b'IEND':
            saw_end = size == 0
        offset = end
    if offset != len(raw) or not (saw_header and saw_data and saw_end):
        raise MaterialError('Incomplete rendered PNG.')
    return raw


def state_equal(actual, expected):
    return (isinstance(actual, dict) and actual.get('jacket_color') == expected['jacket_color']
            and actual.get('accessory') == expected['accessory']
            and type(actual.get('scale')) in (float, int) and abs(actual['scale'] - expected['scale']) < .0001)


def state_caption(state):
    return f"{COLORS[state['jacket_color']]}外衣 · {ACCESSORIES[state['accessory']]} · 比例 {state['scale']:.2f}"


STYLE = '''@page{size:A4;margin:12mm}*{box-sizing:border-box}body{font-family:system-ui,"Microsoft YaHei","Noto Sans CJK SC",sans-serif;color:#1b342e;background:#edf3ed;margin:0;padding:24px}main{max-width:1000px;margin:auto;background:white;padding:28px;border:1px solid #d6e2d7;border-radius:18px}h1{font-size:26px;margin:0 0 16px}h2{font-size:16px}p{line-height:1.7}.goal{font-size:19px;font-weight:600}.views,.targets{display:flex;flex-wrap:wrap;gap:6mm;align-items:flex-start}figure{width:52mm;margin:0}img{display:block;width:52mm;height:69.333mm;border:1px solid #dbe3de;background:#f1f4f2}figcaption{font-size:12px;line-height:1.6;margin-top:6px}.note{font-size:12px;color:#536a5e;border-top:1px solid #dce5de;padding-top:12px;margin-top:20px}a{color:#235b48}li{margin:12px 0}@media print{body{padding:0;background:white}main{padding:0;border:0;border-radius:0}a{color:inherit}.views,figure{break-inside:avoid}}'''


def card_html(card, image_data):
    def figure(item, label):
        data = base64.b64encode(image_data[item['image']]).decode('ascii')
        return ('<figure><img alt="' + label + '" src="data:image/png;base64,' + data + '"><figcaption>'
                + html.escape(state_caption(item['state'])) + '</figcaption></figure>')
    initial = figure(card['initial'], '起始外形')
    targets = ''.join(figure(item, '可接受的目标外形') for item in card['targets'])
    alternative = '以下目标均可接受，任选其一即可。' if len(card['targets']) > 1 else '请达到以下目标外形。'
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>目标外形</title><style>' + STYLE + '</style><main><h1>目标外形</h1><p class="goal">'
            + html.escape(card['goal_text']) + '</p><p>' + alternative + '</p><div class="views"><section><h2>起始外形</h2>'
            + initial + '</section><section><h2>可接受的目标外形</h2><div class="targets">' + targets
            + '</div></section></div><p class="note">图像使用相同视角、相机距离与显示尺寸，大小可以直接比较。请按自己的意图描述目标；若系统追问，请如实回答。</p></main></html>')


def publish_bundle(output, source=SOURCE, avatar_source=AVATAR_SOURCE, renderer_source=RENDERER_SOURCE):
    output = Path(output).resolve()
    manifest_path = safe_file(output, 'render-jobs.json')
    manifest = load_json(manifest_path)
    if manifest != build_manifest(source, avatar_source, renderer_source):
        raise MaterialError('Sources or render jobs changed; prepare and render again.')
    receipt_path = safe_file(output, 'render-receipt.json')
    receipt = load_json(receipt_path)
    if (not isinstance(receipt, dict) or receipt.get('schema_version') != 'appearance-task-card-render-v1'
            or receipt.get('manifest_sha256') != digest_bytes(manifest_path.read_bytes())):
        raise MaterialError('Renderer receipt is absent or does not match the manifest.')
    entries = receipt.get('images')
    if (not isinstance(entries, list) or len(entries) != len(manifest['jobs'])
            or any(not isinstance(entry, dict) or not isinstance(entry.get('id'), str) for entry in entries)
            or len({entry['id'] for entry in entries}) != len(entries)):
        raise MaterialError('Renderer receipt must contain every image exactly once.')
    by_id = {entry['id']: entry for entry in entries}
    images, hashes = {}, {}
    for job in manifest['jobs']:
        entry = by_id.get(job['id'], {})
        if entry.get('image') != job['image'] or not state_equal(entry.get('observed'), job['state']):
            raise MaterialError('Rendered appearance differs from the requested target.')
        raw = png_bytes(safe_file(output, job['image']))
        if entry.get('sha256') != digest_bytes(raw):
            raise MaterialError('Rendered PNG hash differs from its editor receipt.')
        images[job['image']] = raw
        hashes[job['image']] = digest_bytes(raw)
    # No HTML is published until all real image files and observed states pass.
    links = []
    for card in manifest['cards']:
        filename = card['task_id'] + '.html'
        raw = card_html(card, images).encode('utf-8')
        safe_file(output, filename).write_bytes(raw)
        hashes[filename] = digest_bytes(raw)
        links.append('<li><a href="' + filename + '">' + card['task_id'] + '</a> · 可接受目标 '
                     + str(len(card['targets'])) + ' 种</li>')
    index = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>研究者目标卡索引</title><style>' + STYLE
             + '</style><main><h1>研究者目标卡索引</h1><p>研究者专用。按冻结分配表选择单张卡，在线下向参与者出示；不要展示本索引。'
             '这些是任务材料，不是实际参与者数据。</p><ul>' + ''.join(links) + '</ul></main></html>')
    safe_file(output, 'index.html').write_text(index, encoding='utf-8')
    hashes['index.html'] = digest_bytes(index.encode('utf-8'))
    hashes['render-jobs.json'] = digest_bytes(manifest_path.read_bytes())
    hashes['render-receipt.json'] = digest_bytes(receipt_path.read_bytes())
    write_json(safe_file(output, 'source-hashes.json'), {'schema_version': 'appearance-task-card-provenance-v1',
               'purpose': manifest['purpose'], 'source_path': str(Path(source).resolve()),
               'source_sha256': manifest['source_sha256'], 'avatar_source_sha256': manifest['avatar_source_sha256'],
               'renderer_source_sha256': manifest['renderer_source_sha256'], 'render_settings': SETTINGS,
               'unity_version': receipt.get('unity_version'), 'render_mode': receipt.get('render_mode'),
               'files_sha256': hashes})
    return {'state': 'published_offline_materials', 'cards': len(manifest['cards']),
            'images': len(images), 'index': str(output / 'index.html')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'publish'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        output = args.output.expanduser().resolve()
        boundary = (ROOT / 'StudyData/pico').resolve()
        if output == boundary or boundary not in output.parents:
            raise MaterialError('Output must be a subfolder of repository StudyData/pico, outside APK assets.')
        result = prepare_bundle(output) if args.operation == 'prepare' else publish_bundle(output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (MaterialError, OSError) as exc:
        print('Materials error: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
