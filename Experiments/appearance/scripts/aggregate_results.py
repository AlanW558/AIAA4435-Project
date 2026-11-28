#!/usr/bin/env python3
"""Validate and aggregate appearance-module exports using only Python's stdlib.

This independent public package snapshots the questionnaire and evidence contract;
it does not import the private execution batch or change any participant answer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import statistics

PACKAGE = Path(__file__).resolve().parents[1]
CONDITIONS = ('E', 'A', 'N', 'S')
IDS = ('A0', 'A1', 'A2', 'A3', 'A4')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError('Non-finite JSON number: ' + value)


def load(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=_nonfinite)


def validate(record, evidence):
    """Mirror the published module contract without requiring unpublished tools."""
    keys = {'schema', 'questionnaire_version', 'domain', 'collection_unit',
            'collection_mode', 'status', 'participant_id', 'evidence', 'request_source',
            'clarification_source', 'conditions', 'preference', 'comment',
            'review_opened', 'saved_at'}
    if not isinstance(record, dict) or set(record) != keys:
        raise ValueError('Unexpected appearance export fields.')
    expected = {'schema': 'appearance-summary-feedback-v1',
                'questionnaire_version': 'appearance-module-A0-A4-v1',
                'domain': 'appearance', 'collection_unit': 'module',
                'collection_mode': 'api_assisted_output_review', 'status': 'final',
                'request_source': evidence.get('request_source', 'user_supplied_text'),
                'clarification_source': 'assistant_authored_user_authorized'}
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError('Only final exports from the approved appearance questionnaire are accepted.')
    if record['evidence'] != evidence:
        raise ValueError('Mixed or altered release evidence: do not pool these exports.')
    pid = record['participant_id']
    if not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', pid):
        raise ValueError('Use an anonymous participant code.')
    if not isinstance(record['conditions'], dict) or set(record['conditions']) != set(CONDITIONS):
        raise ValueError('Exactly four strategies are required.')
    for condition in CONDITIONS:
        entry = record['conditions'][condition]
        if not isinstance(entry, dict) or set(entry) != {'answers'}:
            raise ValueError('Invalid strategy entry.')
        answers = entry['answers']
        if not isinstance(answers, dict) or set(answers) != set(IDS):
            raise ValueError('Each strategy needs all five A0–A4 items.')
        for answer in answers.values():
            if not isinstance(answer, dict) or set(answer) != {'status', 'value'}:
                raise ValueError('Invalid rating fields.')
            status, value = answer['status'], answer['value']
            numeric = status == 'answered' and type(value) is int and 1 <= value <= 7
            missing = status == 'unable_to_judge' and value is None
            if not (numeric or missing):
                raise ValueError('Final ratings require 1–7 or explicit Unable to judge/null.')
    pref = record['preference']
    if not isinstance(pref, dict) or set(pref) != {'status', 'value'}:
        raise ValueError('Invalid preference fields.')
    status, value = pref['status'], pref['value']
    valid = status == 'no_preference' and value is None
    valid |= (status == 'answered' and isinstance(value, list) and 1 <= len(value) <= 4
              and all(c in CONDITIONS for c in value) and len(set(value)) == len(value))
    if not valid:
        raise ValueError('Preference must be multiple strategies or exclusive No preference.')
    if not isinstance(record['comment'], str) or len(record['comment']) > 4000:
        raise ValueError('Invalid comment.')
    allowed = {t['task_code'] + '/' + c for t in evidence['tasks'] for c in CONDITIONS}
    opened = record['review_opened']
    if not isinstance(opened, list) or any(x not in allowed for x in opened) or len(opened) != len(set(opened)):
        raise ValueError('Invalid image-opened metadata; it is not task-completion evidence.')
    if not isinstance(record['saved_at'], str):
        raise ValueError('A final export needs its saved timestamp.')
    try:
        timestamp = datetime.fromisoformat(record['saved_at'].replace('Z', '+00:00'))
        if timestamp.utcoffset() is None:
            raise ValueError('Missing timezone.')
    except (ValueError, TypeError):
        raise ValueError('Invalid saved timestamp.') from None
    return record


def aggregate(paths, *, evidence, source_manifest=None):
    """Deterministic rebuild: each ID appears once and all raw exports survive."""
    manifest = source_manifest or {'participants': []}
    entries = manifest.get('participants', [])
    known = {e['stored_filename']: e for e in entries}
    if len(known) != len(entries):
        raise ValueError('Duplicate filenames in source manifest.')
    records, sources, seen = [], [], set()
    for path in paths:
        path = Path(path)
        raw = path.read_bytes()
        record = validate(load(path), evidence)
        pid = record['participant_id']
        if pid.casefold() in seen:
            raise ValueError('Duplicate participant ID: ' + pid)
        seen.add(pid.casefold())
        provenance = known.get(path.name)
        if provenance and (provenance['sha256'] != sha(raw) or provenance['participant_id'] != pid):
            raise ValueError('Original download checksum or participant identity changed: ' + path.name)
        sources.append({'participant_id': pid, 'stored_filename': path.name,
                        'original_download_filename': provenance['original_download_filename'] if provenance else path.name,
                        'sha256': sha(raw), 'saved_at': record['saved_at']})
        records.append(deepcopy(record))
    if not records:
        raise ValueError('No participant exports found.')
    records.sort(key=lambda r: r['participant_id'])
    sources.sort(key=lambda r: r['participant_id'])
    n = len(records)
    rows = [{'participant_id': record['participant_id'], 'domain': 'appearance',
             'condition': c, 'item_id': item, **record['conditions'][c]['answers'][item]}
            for record in records for c in CONDITIONS for item in IDS]
    summaries = {}
    for c in CONDITIONS:
        summaries[c] = {}
        for item in IDS:
            answers = [r['conditions'][c]['answers'][item] for r in records]
            values = [a['value'] for a in answers if a['status'] == 'answered']
            dist = Counter(values)
            summaries[c][item] = {
                'n_total': n, 'n_numeric': len(values), 'n_unable_to_judge': n - len(values),
                'mean': statistics.mean(values) if values else None,
                'median': statistics.median(values) if values else None,
                'sample_sd': statistics.stdev(values) if len(values) >= 2 else None,
                'distribution': {str(v): dist[v] for v in range(1, 8)}}
    selected = Counter(c for r in records if r['preference']['status'] == 'answered'
                       for c in r['preference']['value'])
    no_preference = sum(r['preference']['status'] == 'no_preference' for r in records)
    return {
        'schema': 'appearance-aggregate-results-v1',
        'questionnaire_version': 'appearance-module-A0-A4-v1',
        'response_schema': 'appearance-summary-feedback-v1',
        'domain': 'appearance', 'collection_unit': 'module',
        'collection_mode': 'api_assisted_output_review',
        'release_id': sha(canonical(evidence)), 'evidence': deepcopy(evidence),
        'participant_namespace': 'appearance_output_review_only',
        'participant_count': n, 'participant_ids': [r['participant_id'] for r in records],
        'source_files': sources, 'participant_records': records,
        'rating_rows': rows, 'rating_row_count': len(rows),
        'numeric_rating_count': sum(r['status'] == 'answered' for r in rows),
        'unable_to_judge_count': sum(r['status'] == 'unable_to_judge' for r in rows),
        'ratings_by_condition_and_item': summaries,
        'preference_summary': {
            'multiple_selection': True, 'participant_denominator': n,
            'participants_selecting_strategies': n - no_preference,
            'selection_counts': {c: selected[c] for c in CONDITIONS},
            'selection_proportions_of_all_participants': {c: selected[c] / n for c in CONDITIONS},
            'total_strategy_selections': sum(selected.values()),
            'no_preference_count': no_preference, 'no_preference_proportion': no_preference / n},
        'analysis_notes': [
            'The same participant evaluates all four strategies; observations are paired.',
            'All participants review the same frozen API-generated outcomes and clarification record.',
            'Clarification replies were assistant-authored under user authorization, not independently generated by each participant.',
            'A0–A4 are reported separately; no validated overall scale score is computed.',
            'Unable to judge is excluded from numeric summaries and counted separately, never replaced with 4 or 0.',
            'Preference is multiple selection; proportions use all participants and may sum above 1.',
            'Participant codes are local to this appearance dataset; matching codes in another study do not establish shared identity.',
            'Module scores cannot be converted into per-task or per-scenario subjective ratings.',
            'These are descriptive results; no population-level superiority or significance is inferred.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=PACKAGE / 'results')
    parser.add_argument('--output', type=Path, default=PACKAGE / 'results/aggregate_results.json')
    parser.add_argument('--evidence', type=Path, default=PACKAGE / 'materials/review_evidence.json')
    parser.add_argument('--source-manifest', type=Path, default=PACKAGE / 'source_manifest.json')
    args = parser.parse_args()
    lock = load(args.evidence)
    evidence = lock['evidence']
    if lock.get('schema') != 'appearance-feedback-evidence-lock-v1' or lock['release_id'] != sha(canonical(evidence)):
        raise ValueError('The evidence lock does not match its release hash.')
    paths = sorted(set(args.input_dir.glob('participant_*.json')) |
                   set(args.input_dir.glob('P*_appearance_feedback_*.json')))
    if args.output.resolve() in {p.resolve() for p in paths}:
        raise ValueError('Aggregate output must not overwrite a participant source.')
    result = aggregate(paths, evidence=evidence, source_manifest=load(args.source_manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps({'participants': result['participant_count'],
                      'rating_rows': result['rating_row_count'],
                      'numeric_ratings': result['numeric_rating_count'],
                      'unable_to_judge': result['unable_to_judge_count'],
                      'preference_counts': result['preference_summary']['selection_counts'],
                      'release_id': result['release_id']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
