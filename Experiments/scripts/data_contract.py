"""Local, lossless participant records and descriptive aggregation. No API calls."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/TutorTextCheck'))
from attribute_feedback import validate_feedback, CONDITIONS, IDS, BUNDLE_SCHEMA, VERSION, NUMERIC_SINGLE_VERSION

DOMAINS = ('speech_rate', 'reply_length', 'tone', 'voice')
CONSTRUCTS = dict(zip(IDS, ('Requirement fulfillment', 'Ease of adjustment', 'Perceived control', 'Clarification appropriateness', 'Overall satisfaction')))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    temporary.replace(path)


def participant_filename(participant_id):
    if not re.fullmatch(r'P[0-9]{3,}', participant_id):
        raise ValueError('Use P001, P002, ... as participant_id.')
    return f'participant_{participant_id[1:]}.json'


def normalize_preference(pref):
    choices = pref['value'] if isinstance(pref['value'], list) else [pref['value']]
    return {'status': pref['status'], 'choices': choices if pref['status'] == 'answered' else [],
            'source_status': pref['status'], 'source_value': deepcopy(pref['value']), 'amendment_id': None}


def validate_choices(choices):
    return (isinstance(choices, list) and (choices == ['no_preference'] or
            1 <= len(choices) <= 4 and all(isinstance(c, str) and c in CONDITIONS for c in choices)
            and len(set(choices)) == len(choices)))


def build_participant(raw, participant_id, display_label, review, amendments=None, provenance=None):
    participant_filename(participant_id)
    source = json.loads(raw)
    if (not isinstance(source, dict) or set(source) != {'schema', 'batch_id', 'questionnaire_version', 'kind', 'exported_at', 'records'}
            or not isinstance(source.get('exported_at'), str)):
        raise ValueError('Invalid completed-attributes export fields.')
    version = source.get('questionnaire_version')
    if version not in (NUMERIC_SINGLE_VERSION, VERSION):
        raise ValueError('This numeric analysis accepts questionnaire v2 or v3 only; never recode categorical v1.')
    if source.get('schema') != BUNDLE_SCHEMA or source.get('kind') != 'completed_attributes':
        raise ValueError('Import the completed-attributes download, not a draft backup or task-level feedback.')
    if source.get('batch_id') != review['batch_id']:
        raise ValueError('Feedback and review package batch IDs differ.')
    current = deepcopy(review)
    current['questionnaire_version'] = version
    records = source.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('At least one completed attribute is required.')
    validated = [validate_feedback(record, current, final=True) for record in records]
    domains = [record['domain'] for record in validated]
    if len(domains) != len(set(domains)) or any(d not in DOMAINS for d in domains):
        raise ValueError('Duplicate or unsupported attribute.')
    task_releases = {g['domain']: g['task_releases'] for g in review['attributes']}
    if set(task_releases) != set(DOMAINS):
        raise ValueError('Review package must include all four attributes.')
    cohort = {'batch_id': source['batch_id'], 'source_questionnaire_version': version,
              'task_releases': task_releases, 'collection_unit': 'attribute',
              'collection_method': 'auxiliary_api_review'}
    by_domain = {record['domain']: record for record in validated}
    ratings, preferences, comments = [], [], []
    for domain in DOMAINS:
        record = by_domain.get(domain)
        for condition in CONDITIONS:
            for item in IDS:
                answer = record['conditions'][condition]['answers'][item] if record else {'status': 'not_submitted', 'value': None}
                ratings.append({'domain': domain, 'condition': condition, 'item_id': item, **deepcopy(answer)})
            comments.append({'domain': domain, 'condition': condition,
                             'extras': deepcopy(record['conditions'][condition]['extras']) if record else None})
        pref = normalize_preference(record['preference']) if record else {
            'status': 'not_submitted', 'choices': [], 'source_status': 'not_submitted', 'source_value': None, 'amendment_id': None}
        preferences.append({'domain': domain, **pref})
    amendments = deepcopy(amendments or [])
    seen = set()
    for index, amendment in enumerate(amendments):
        required = {'domain', 'field', 'previous', 'replacement', 'reason', 'authority', 'recorded_on'}
        if not isinstance(amendment, dict) or set(amendment) != required or amendment['field'] != 'preference':
            raise ValueError('Only explicit preference amendments with source, reason and date are supported.')
        domain = amendment['domain']
        if domain not in by_domain or domain in seen:
            raise ValueError('Amendment needs one submitted attribute, once only.')
        seen.add(domain)
        if amendment['previous'] != by_domain[domain]['preference']:
            raise ValueError('Amendment previous value does not match the preserved source export.')
        replacement = amendment['replacement']
        if (not isinstance(replacement, dict) or set(replacement) != {'status', 'value'} or
                replacement['status'] != 'answered' or not validate_choices(replacement['value'])):
            raise ValueError('Amended preference must select strategies or exclusive no_preference.')
        if any(not isinstance(amendment[k], str) or not amendment[k].strip() for k in ('reason', 'authority', 'recorded_on')):
            raise ValueError('An amendment requires a nonempty reason, authority and date.')
        amendment['amendment_id'] = digest(amendment)
        pref = next(p for p in preferences if p['domain'] == domain)
        pref.update(status='answered', choices=deepcopy(replacement['value']), amendment_id=amendment['amendment_id'])
    return {'schema': 'participant-results-v1', 'participant_id': participant_id, 'display_label': display_label,
            'cohort_id': digest(cohort), 'cohort': cohort, 'completion_status': 'complete' if len(validated) == 4 else 'partial_attributes',
            'source': {'filename': 'source_export.json', 'sha256': digest(raw), 'canonical_sha256': digest(source),
                       'questionnaire_version': version, 'exported_at': source.get('exported_at')},
            'source_export': source, 'amendments': amendments, 'ratings': ratings, 'preferences': preferences,
            'comments': comments, 'questionnaire_items': deepcopy(review['items']),
            'provenance': deepcopy(provenance or {'collection_method': 'auxiliary_api_review',
                'request_and_clarification_authorship': 'See per-task review annotations; not inferred as participant speech.',
                'formal_vr_study': False})}


def import_participant(source_path, participant_id, display_label, review_path, output_directory, amendments=None, provenance=None):
    raw = Path(source_path).read_bytes()
    result = build_participant(raw, participant_id, display_label, read(review_path), amendments, provenance)
    directory = Path(output_directory)
    destination = directory / participant_filename(participant_id)
    source_relative = f'source_exports/{participant_id}-{result["source"]["sha256"]}.json'
    result['source']['filename'] = source_relative
    if destination.exists():
        if read(destination) != result:
            raise ValueError(f'{participant_id} already exists with different content. Refusing to overwrite; resolve identity/correction explicitly.')
        return destination, False
    for existing_path in directory.glob('participant_[0-9]*.json'):
        existing = read(existing_path)
        if digest(existing['source_export']) == result['source']['canonical_sha256']:
            raise ValueError(f'This source export is already registered as {existing["participant_id"]}; refusing to count the same download as a different participant.')
    # Preserve exact bytes separately; source_export inside the participant file preserves the full JSON value.
    source_copy = directory / source_relative
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    if source_copy.exists() and source_copy.read_bytes() != raw:
        raise ValueError('Source preservation collision.')
    if not source_copy.exists():
        with source_copy.open('xb') as stream:
            stream.write(raw)
    atomic_json(destination, result)
    return destination, True


def aggregate(participants):
    ids = [p['participant_id'] for p in participants]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate participant ID; one participant file is counted once.')
    exports = [digest(p['source_export']) for p in participants]
    if len(exports) != len(set(exports)):
        raise ValueError('Duplicate source export across participant IDs; the same download cannot count as multiple participants.')
    cohorts = {}
    for p in sorted(participants, key=lambda p: p['participant_id']):
        if p.get('schema') != 'participant-results-v1' or digest(p['cohort']) != p['cohort_id']:
            raise ValueError('Invalid participant schema or cohort identity.')
        # Recompute normalized rows from the immutable source + explicit amendment.
        # Manually edited normalized scores must never silently enter aggregation.
        review = {'batch_id': p['cohort']['batch_id'], 'items': p['questionnaire_items'],
                  'attributes': [{'domain': domain, 'task_releases': releases, 'status': 'published'}
                                 for domain, releases in p['cohort']['task_releases'].items()]}
        clean_amendments = [{key: value for key, value in a.items() if key != 'amendment_id'} for a in p['amendments']]
        rebuilt = build_participant(canonical(p['source_export']).encode(), p['participant_id'], p['display_label'],
                                    review, clean_amendments, p['provenance'])
        if p['source']['canonical_sha256'] != digest(p['source_export']):
            raise ValueError('Participant source export checksum changed.')
        for key in ('cohort_id', 'cohort', 'completion_status', 'ratings', 'preferences', 'comments', 'amendments'):
            if p[key] != rebuilt[key]:
                raise ValueError(f'Participant {p["participant_id"]}: {key} differs from source + amendment.')
        cohort = cohorts.setdefault(p['cohort_id'], {'cohort_id': p['cohort_id'], 'definition': p['cohort'],
            'participants': [], 'questionnaire_items': p['questionnaire_items'], 'ratings': [], 'preferences': [], 'comments': []})
        cohort['participants'].append({'participant_id': p['participant_id'], 'display_label': p['display_label'],
            'completion_status': p['completion_status'], 'source_sha256': p['source']['sha256'],
            'source_questionnaire_version': p['source']['questionnaire_version'], 'amendments': p['amendments'],
            'provenance': p['provenance']})
        for key in ('ratings', 'preferences', 'comments'):
            cohort[key].extend({'participant_id': p['participant_id'], **deepcopy(row)} for row in p[key])
    for cohort in cohorts.values():
        cohort['n_participants'] = len(cohort['participants'])
        summaries = []
        for domain in DOMAINS:
            for condition in CONDITIONS:
                for item in IDS:
                    rows = [r for r in cohort['ratings'] if (r['domain'], r['condition'], r['item_id']) == (domain, condition, item)]
                    values = [r['value'] for r in rows if r['status'] == 'answered']
                    summaries.append({'domain': domain, 'condition': condition, 'item_id': item,
                        'n_total': len(rows), 'n_valid': len(values), 'missing_by_status': dict(Counter(r['status'] for r in rows if r['status'] != 'answered')),
                        'values': values, 'distribution': {str(i): values.count(i) for i in range(1, 8)},
                        'mean': statistics.mean(values) if values else None, 'median': statistics.median(values) if values else None})
        cohort['rating_summary'] = summaries
        cohort['preference_summary'] = []
        for domain in DOMAINS:
            rows = [r for r in cohort['preferences'] if r['domain'] == domain]
            answered = [r for r in rows if r['status'] == 'answered']
            cohort['preference_summary'].append({'domain': domain, 'n_total': len(rows), 'n_answered': len(answered),
                'missing_by_status': dict(Counter(r['status'] for r in rows if r['status'] != 'answered')),
                'votes': {c: sum(c in r['choices'] for r in answered) for c in (*CONDITIONS, 'no_preference')},
                'multi_select_respondents': sum(len(r['choices']) > 1 for r in answered)})
    return {'schema': 'aggregate-results-v1', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'n_unique_participants': len(ids), 'cohorts': list(cohorts.values()),
        'constructs': CONSTRUCTS, 'analysis_rules': [
            'Each participant counts once; four attributes are repeated judgments, not four people.',
            'Cohorts are separated by batch, source questionnaire version, task releases and collection method.',
            'Each selected strategy receives one full preference vote; no_preference is exclusive.',
            'Unable/unsubmitted scores are missing, never zero; preserve reasons and valid n.',
            'Describe each construct separately; no combined standardized score or significance claim for n=1.']}
