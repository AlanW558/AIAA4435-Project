"""Attribute-level auxiliary feedback, versioned separately from task ratings.

No model calls and no conversion of earlier per-task answers into summary ratings.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

VERSION = 'attribute-summary-feedback-v3'
LEGACY_VERSION = 'attribute-summary-feedback-v1'
NUMERIC_SINGLE_VERSION = 'attribute-summary-feedback-v2'
SUPPORTED_VERSIONS = (LEGACY_VERSION, NUMERIC_SINGLE_VERSION, VERSION)
SCHEMA = 'tutor-text-attribute-feedback-v1'
BUNDLE_SCHEMA = 'tutor-text-attribute-feedback-bundle-v1'
CONDITIONS = ('E', 'A', 'N', 'S')
IDS = ('A0', 'A1', 'A2', 'A3', 'A4')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def feedback_items(base_items, version=VERSION):
    if version not in SUPPORTED_VERSIONS:
        raise ValueError('Unsupported attribute questionnaire version.')
    wording = {
        'A0': 'Overall, to what extent did this approach’s outcomes meet your requirements across the tasks for this attribute?',
        'A1': 'Overall, how difficult or easy was it to make adjustments to this attribute using this approach?',
        'A2': 'Across the tasks for this attribute, I felt in control of the changes made to the tutor with this approach.',
        'A3': 'This approach’s decisions about whether to ask for clarification suited my needs across the tasks for this attribute.',
        'A4': 'Overall, I am satisfied with my experience of adjusting this attribute using this approach.',
    }
    if [i['id'] for i in base_items] != list(IDS):
        raise ValueError('Expected the five registered base items A0–A4.')
    items = deepcopy(base_items)
    for item in items:
        item['text'] = wording[item['id']]
        item['scope_adaptation'] = 'Attribute-level overall judgment across all included tasks; not a per-task score or a standard-scale total.'
        if item['id'] == 'A0':
            item['help'] = 'Consider the requested changes and settings that should stay unchanged across all tasks for this attribute. Give one overall judgment; individual outcomes may differ.'
            item['scale'] = 'category' if version == LEGACY_VERSION else 'fulfillment7'
            if version != LEGACY_VERSION:
                item['left'] = 'Not at all'
                item['right'] = 'Completely'
            else:
                item.pop('left', None)
                item.pop('right', None)
    return items


def build_attributes(tasks):
    groups = {}
    for task in tasks:
        group = groups.setdefault(task['domain'], {'domain': task['domain'], 'title': task['title'], 'tasks': []})
        group['tasks'].append(task)
    result = []
    for group in groups.values():
        members = group.pop('tasks')
        codes = [task['task_code'] for task in members]
        if len(set(codes)) != len(codes):
            raise ValueError('Duplicate task in attribute group.')
        releases = {t['task_code']: t['release_id'] for t in members if t['status'] == 'published'}
        cards = [card for task in members if task['status'] == 'published' for card in task['conditions'].values()]
        group.update(task_codes=codes, task_releases=releases, release_set_id=digest({'domain': group['domain'], 'task_releases': releases}),
                     status='published' if len(releases) == len(codes) else 'pending',
                     audio_count=sum(bool(c['audio_url']) for c in cards),
                     technical_failure_count=sum(bool(c.get('technical_failure')) for c in cards))
        result.append(group)
    return result


def blank_feedback(batch_id, group, version=VERSION):
    if version not in SUPPORTED_VERSIONS:
        raise ValueError('Unsupported attribute questionnaire version.')
    return {'schema': SCHEMA, 'questionnaire_version': version, 'collection_unit': 'attribute',
            'batch_id': batch_id, 'domain': group['domain'], 'task_releases': deepcopy(group['task_releases']),
            'conditions': {c: {'answers': {i: {'status': 'unanswered', 'value': None} for i in IDS},
                               'extras': {'reasons': [], 'comment': '', 'comment_confirmed': False}} for c in CONDITIONS},
            'preference': {'status': 'unanswered', 'value': None}}


def validate_feedback(data, current, *, final=True):
    expected = {'schema', 'questionnaire_version', 'collection_unit', 'batch_id', 'domain', 'task_releases', 'conditions', 'preference'}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError('Use the attribute feedback format; task feedback cannot be relabelled or averaged.')
    version = current.get('questionnaire_version', VERSION)
    if (version not in SUPPORTED_VERSIONS or data['schema'] != SCHEMA or data['questionnaire_version'] != version
            or data['collection_unit'] != 'attribute' or data['batch_id'] != current['batch_id']):
        raise ValueError('Attribute feedback version, collection unit or batch does not match.')
    groups = {g['domain']: g for g in current['attributes']}
    if not isinstance(data['domain'], str) or data['domain'] not in groups:
        raise ValueError('Unknown attribute.')
    group = groups[data['domain']]
    if group['status'] != 'published' or data['task_releases'] != group['task_releases']:
        raise ValueError('Attribute feedback must reference all current published task releases.')
    if not isinstance(data['conditions'], dict) or set(data['conditions']) != set(CONDITIONS):
        raise ValueError('All four strategies are required.')
    for condition in CONDITIONS:
        section = data['conditions'][condition]
        if not isinstance(section, dict) or set(section) != {'answers', 'extras'}:
            raise ValueError('Invalid strategy feedback fields.')
        answers = section['answers']
        if not isinstance(answers, dict) or set(answers) != set(IDS):
            raise ValueError('Each strategy requires exactly five answers.')
        for item, answer in answers.items():
            if not isinstance(answer, dict) or set(answer) != {'status', 'value'}:
                raise ValueError('Each answer needs an explicit status and value.')
            status, value = answer['status'], answer['value']
            if status == 'answered':
                valid = value in ('fully_met', 'partly_met', 'not_met') if item == 'A0' and version == LEGACY_VERSION else type(value) is int and 1 <= value <= 7
            else:
                valid = value is None and (status == 'unable_to_judge' or (not final and status == 'unanswered'))
            if not valid:
                raise ValueError('Unresolved or invalid attribute answer.')
        extra = section['extras']
        if (not isinstance(extra, dict) or set(extra) != {'reasons', 'comment', 'comment_confirmed'}
                or extra['reasons'] != [] or not isinstance(extra['comment'], str) or len(extra['comment']) > 4000
                or type(extra['comment_confirmed']) is not bool or extra['comment_confirmed'] != bool(extra['comment'])):
            raise ValueError('Invalid optional attribute comment.')
    pref = data['preference']
    if not isinstance(pref, dict) or set(pref) != {'status', 'value'}:
        raise ValueError('An explicit strategy preference is required.')
    if pref['status'] == 'answered':
        value = pref['value']
        if version == VERSION:
            valid = (isinstance(value, list) and (value == ['no_preference'] or
                     1 <= len(value) <= 4 and all(isinstance(c, str) and c in CONDITIONS for c in value)
                     and len(value) == len(set(value))))
        else:
            valid = value in (*CONDITIONS, 'no_preference')
    else:
        valid = pref['value'] is None and ((version != VERSION and pref['status'] == 'unable_to_judge')
                                          or (not final and pref['status'] == 'unanswered'))
    if not valid:
        raise ValueError('Choose a strategy preference using the registered version: one or more strategies, or exclusive no preference.')
    return deepcopy(data)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def save_submission(directory, data, current):
    """Validate every record before saving an individual or completed bundle."""
    bundle = isinstance(data, dict) and data.get('schema') == BUNDLE_SCHEMA
    if bundle:
        if (set(data) != {'schema', 'batch_id', 'questionnaire_version', 'kind', 'exported_at', 'records'}
                or data['batch_id'] != current['batch_id'] or data['questionnaire_version'] != current.get('questionnaire_version', VERSION)
                or data['kind'] != 'completed_attributes' or not isinstance(data['exported_at'], str)
                or not isinstance(data['records'], list) or not data['records']):
            raise ValueError('Import a completed-attributes bundle; draft backups are not final feedback.')
        records = [validate_feedback(record, current) for record in data['records']]
        if len({record['domain'] for record in records}) != len(records):
            raise ValueError('Duplicate attribute in feedback bundle.')
    else:
        records = [validate_feedback(data, current)]
    paths = []
    for record in records:
        identity = digest(record)
        folder = Path(directory) / 'attribute-feedback' / record['domain']
        destination = folder / (identity + '.json')
        if not destination.exists():
            previous = [saved for p in folder.glob('*.json') if (saved := json.loads(p.read_text())).get('questionnaire_version') == record['questionnaire_version']]
            latest = max(previous, key=lambda r: r['saved_at']) if previous else None
            saved = {**record, 'saved_at': datetime.now(timezone.utc).isoformat(), 'collection_kind': 'engineering',
                     'input_source': 'user_supplied_text', 'formal_study_submission': False,
                     'submission_id': identity, 'answers_sha256': identity,
                     'supersedes': latest['submission_id'] if latest else None}
            atomic_json(destination, saved)
        paths.append(str(destination))
    return paths if bundle else paths[0]
