#!/usr/bin/env python3
"""Package published results with local relative audio, without invoking a model."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/TutorTextCheck'))
import report
from data_contract import atomic_json, digest


def walk_audio(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'audio_url' and isinstance(child, str):
                yield child
            else:
                yield from walk_audio(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_audio(child)


def embedded_data(page):
    match = re.search(r'<script[^>]*id="report-data"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        raise ValueError('Original review page lacks its embedded review data.')
    return json.loads(match.group(1))


def build(directory, output, preserve_v2=False):
    directory, output = directory.resolve(), output.resolve()
    if output.exists():
        raise ValueError('Output must be a new directory; never overwrite a released review package.')
    data = report.collect(directory, questionnaire_version='attribute-summary-feedback-v3')
    if any(task['status'] != 'published' for task in data['tasks']):
        raise ValueError('Publish every task and finish clarification before packaging results.')
    old_page = None
    audio_urls = set(walk_audio(data))
    if preserve_v2:
        old_page = (directory / 'REVIEW_AND_QUESTIONNAIRE.html').read_bytes()
        old_data = embedded_data(old_page.decode('utf-8'))
        if old_data['questionnaire_version'] != 'attribute-summary-feedback-v2' or old_data['batch_id'] != data['batch_id']:
            raise ValueError('Requested v2 snapshot is not the same batch original v2 page.')
        if {g['domain']: g['task_releases'] for g in old_data['attributes']} != {g['domain']: g['task_releases'] for g in data['attributes']}:
            raise ValueError('Original page refers to different result releases.')
        audio_urls.update(walk_audio(old_data))
    # Validate every path and hash before creating output. Only referenced WAVs are copied.
    audio = []
    for url in sorted(audio_urls):
        relative = unquote(url)
        path = report.inside(directory, relative)
        if not relative.startswith('audio/') or path.suffix.lower() != '.wav':
            raise ValueError('Only relative audio/*.wav assets are allowed.')
        raw = path.read_bytes()
        if raw.startswith(b'version https://git-lfs.github.com/spec'):
            raise ValueError('Found a Git LFS pointer; download the actual audio first.')
        audio.append({'path': relative, 'sha256': digest(raw), 'bytes': len(raw)})
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False)
    if '/Users/' in serialized or re.search(r'sk-(?:sp-)?[A-Za-z0-9._-]{15,}', serialized):
        raise ValueError('Private path or apparent credential in public review data; inspect before packaging.')
    output.mkdir(parents=True)
    for asset in audio:
        target = output / asset['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(directory / asset['path'], target)
    safe = serialized.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (output / 'REVIEW_AND_QUESTIONNAIRE.html').write_text(report.PAGE.replace('__DATA__', safe), encoding='utf-8')
    atomic_json(output / 'review-data.json', data)
    if old_page is not None:
        (output / 'REVIEW_AND_QUESTIONNAIRE_v2.html').write_bytes(old_page)
    metadata = json.loads((directory / 'batch.json').read_text())
    try:
        source_directory = directory.relative_to(ROOT).as_posix()
    except ValueError:
        source_directory = directory.name
    manifest = {'schema': 'portable-review-manifest-v1', 'batch_id': data['batch_id'],
        'source_directory': source_directory, 'created_at': metadata['created_at'],
        'catalog_sha256': metadata['catalog_sha256'], 'catalog_version': json.loads((directory / 'catalog.json').read_text()).get('version'),
        'source_questionnaire_version': metadata['questionnaire_version'], 'display_questionnaire_version': data['questionnaire_version'],
        'model': metadata.get('model_profile', {}).get('model'), 'tts_model': metadata.get('tts_profile', {}).get('model'),
        'collection_method': 'auxiliary_api_review', 'formal_vr_study': False,
        'request_provenance': 'Requests were drafted/revised by the assistant with user authorization.',
        'clarification_provenance': 'Actual clarification questions and authorized assistant-authored answers are retained per strategy.',
        'audio_timing_note': 'This text-check-v4 audio was generated before the subsequent clarification repair; packaging does not rerun or repair these outcomes.' if directory.name == 'text-check-v4' else 'Audio is copied unchanged from the identified batch; no calls are made by this packaging command.',
        'tasks': len(data['tasks']), 'audio_count': len(audio), 'audio_assets': audio,
        'files': {p.name: digest(p.read_bytes()) for p in output.glob('*') if p.is_file()},
        'source_v2_page_sha256': digest(old_page) if old_page is not None else None,
        'excluded': ['credentials', 'debug logs', 'checkpoints', 'runtime environment', 'private absolute paths'],
        'participant_answers_prefilled': False}
    atomic_json(output / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preserve-v2', action='store_true')
    args = parser.parse_args()
    result = build(args.directory, args.output, args.preserve_v2)
    print(f'Packaged {result["tasks"]} tasks, {result["audio_count"]} audio files; provider calls: 0')

if __name__ == '__main__':
    main()
