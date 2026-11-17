"""New study questionnaire validation; deliberately separate from legacy debug feedback."""
from copy import deepcopy
from core import APIError

ATTRIBUTE_VERSION = 'attribute-feedback-v3'
NATURAL_VERSION = 'natural-selective-feedback-v2'
PREFERENCE_VERSION = 'strategy-preference-v1'
ATTRIBUTE_IDS = tuple(f'A{i}' for i in range(5))
NATURAL_IDS = tuple(f'N{i}' for i in range(8)) + tuple(f'S{i}' for i in range(1, 11)) + tuple(f'U{i}' for i in range(1, 9))
REASONS = {'target_mismatch', 'unwanted_change', 'not_maintained', 'hard_to_verify', 'interaction_problem', 'other'}


def reject(message):
    raise APIError(400, 'invalid_study_answer', message)


def validate_answers(version, answers, *, final=False):
    ids = ATTRIBUTE_IDS if version == ATTRIBUTE_VERSION else NATURAL_IDS if version == NATURAL_VERSION else None
    if ids is None or not isinstance(answers, dict) or set(answers) - set(ids):
        reject('Use the registered questionnaire version and item IDs.')
    result = {}
    for item in ids:
        a = deepcopy(answers.get(item, {'status': 'unanswered', 'value': None}))
        if not isinstance(a, dict) or set(a) - {'status', 'value', 'reason'} or not {'status', 'value'} <= set(a):
            reject('Each answer requires an explicit status and value.')
        status, value = a['status'], a['value']
        standard = item.startswith(('S', 'U'))
        if status == 'answered':
            if item in ('A0', 'N0'):
                if value not in ('fully_met', 'partly_met', 'not_met'): reject('Invalid outcome category.')
            elif type(value) is not int or not 1 <= value <= (5 if item.startswith('S') else 7):
                reject('Use an integer in the item scale, not a default or boolean.')
        else:
            if value is not None: reject('Non-numeric statuses must have a null value.')
            if status == 'unable_to_judge':
                if standard: reject('Standard scales do not have an unable-to-judge position.')
            elif status == 'not_applicable':
                if item != 'N5' or a.get('reason') != 'no_clarification_questions': reject('Only N5 supports this non-applicable reason.')
            elif status in ('skipped', 'unanswered', 'technical_missing'):
                if status == 'technical_missing' and (not isinstance(a.get('reason'), str) or not 1 <= len(a['reason']) <= 200):
                    reject('Technical missingness requires a bounded reason code.')
                if final and not (standard and status == 'skipped'): reject('Unresolved core answers cannot be submitted.')
            else: reject('Unknown answer status.')
        if 'reason' in a and status not in ('technical_missing', 'not_applicable'): reject('Reason is not applicable to this status.')
        result[item] = a
    return result


def extras(value, answers, *, natural=False, later_interaction=False):
    if not isinstance(value, dict) or set(value) - {'reasons', 'comment', 'comment_confirmed'}: reject('Invalid optional answer fields.')
    comment = value.get('comment', '')
    if not isinstance(comment, str) or len(comment) > 4000: reject('Comment must be bounded text.')
    if type(value.get('comment_confirmed', False)) is not bool: reject('Text confirmation must be boolean.')
    if comment and value.get('comment_confirmed') is not True: reject('Only confirmed STT comments may be saved.')
    reasons = value.get('reasons', [])
    if not isinstance(reasons, list) or any(not isinstance(r, str) or r not in REASONS for r in reasons) or len(reasons) != len(set(reasons)):
        reject('Invalid reason codes.')
    if reasons and (natural or answers['A0']['value'] == 'fully_met' or answers['A0']['status'] not in ('answered', 'unable_to_judge')):
        reject('Reasons do not apply to this answer.')
    if 'not_maintained' in reasons and not later_interaction: reject('No later interaction was registered.')
    return {'reasons': reasons, 'comment': comment, 'comment_confirmed': bool(comment)}


def completeness(answers):
    return 'complete' if all(a['status'] in ('answered', 'unable_to_judge', 'not_applicable') for a in answers.values()) else 'partial'


def scores(answers):
    def score(ids, transform, multiplier=1):
        valid = [answers[i]['value'] for i in ids if answers[i]['status'] == 'answered']
        return {'value': transform(valid) * multiplier if len(valid) == len(ids) else None,
                'n_answered': len(valid), 'score_status': 'valid' if len(valid) == len(ids) else 'insufficient_items'}
    return {'scoring_version': 'natural-scoring-v1',
            'sus': score([f'S{i}' for i in range(1, 11)], lambda xs: sum(x - 1 if i % 2 == 0 else 5 - x for i, x in enumerate(xs)), 2.5),
            'ueq_pragmatic': score([f'U{i}' for i in range(1, 5)], lambda xs: sum(x - 4 for x in xs) / 4),
            'ueq_hedonic': score([f'U{i}' for i in range(5, 9)], lambda xs: sum(x - 4 for x in xs) / 4)}
