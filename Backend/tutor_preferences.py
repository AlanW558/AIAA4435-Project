"""Practice sequence boundaries and explicit strategy preferences; no model context."""
from copy import deepcopy
from datetime import datetime, timezone
import uuid
from core import APIError, IDENTIFIER, text_value
from tutor_study_materials import is_preview, validate_plan

VERSION = 'strategy-preference-v1'
DOMAINS = ('speech_rate', 'reply_length', 'tone', 'voice')
CONDITIONS = ('E', 'A', 'N', 'S')


def validate_sequence(value):
    if value is None:
        return None
    if isinstance(value, dict) and is_preview(value):
        return validate_plan(value)
    if not isinstance(value, dict) or set(value) != {'version', 'purpose', 'modules'} or value['version'] != 'attribute-sequence-v1' or value['purpose'] != 'practice':
        raise APIError(400, 'invalid_sequence', 'Use a versioned practice attribute sequence.')
    modules = value['modules']; domains = set(); codes = set()
    if not isinstance(modules, list) or not 1 <= len(modules) <= 4:
        raise APIError(400, 'invalid_sequence', 'Use one to four attribute modules.')
    for module in modules:
        if not isinstance(module, dict) or set(module) != {'domain', 'tasks'} or not isinstance(module['domain'], str) or module['domain'] not in DOMAINS or module['domain'] in domains:
            raise APIError(400, 'invalid_sequence', 'Use unique attribute modules; no private instructions.')
        domains.add(module['domain']); tasks = module['tasks']
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 32:
            raise APIError(400, 'invalid_sequence', 'Use a nonempty task list.')
        for task in tasks:
            if not isinstance(task, dict) or set(task) != {'task_code', 'scenario'}:
                raise APIError(400, 'invalid_sequence', 'Only task codes and scenarios belong in the sequence.')
            code, scenario = task['task_code'], task['scenario']
            if not isinstance(code, str) or not IDENTIFIER.fullmatch(code) or len(code) > 64 or code in codes or not isinstance(scenario, str) or scenario not in ('C1', 'C2', 'C3', 'C4'):
                raise APIError(400, 'invalid_sequence', 'Use unique task codes and valid scenarios.')
            codes.add(code)
    return deepcopy(value)


def slots(sequence):
    return [(m, t, {'domain': module['domain'], **task}) for m, module in enumerate(sequence['modules']) for t, task in enumerate(module['tasks'])]


def sequence_view(rt):
    if rt.sequence is None:
        return {'registered': False, 'preference_scope': ''}
    plan = slots(rt.sequence); index = rt.sequence_index - 1
    mi, ti, spec = plan[index]
    end = ti == len(rt.sequence['modules'][mi]['tasks']) - 1
    last = index == len(plan) - 1
    all_attributes = set(m['domain'] for m in rt.sequence['modules']) == set(DOMAINS)
    scope = ''
    if end and rt.lifecycle == 'submitted' and not rt.next_task_id and not rt.preference_exited:
        if 'attribute' not in rt.preferences: scope = 'attribute'
        elif last and all_attributes and 'comparison_overall' not in rt.preferences: scope = 'comparison_overall'
    done = last and rt.lifecycle == 'submitted' and 'attribute' in rt.preferences and (not all_attributes or 'comparison_overall' in rt.preferences)
    return {'registered': True, 'module_index': mi, 'module_task_index': ti, 'at_module_end': end,
            'has_next_module': mi + 1 < len(rt.sequence['modules']), 'has_next_in_module': not end,
            'all_attributes': all_attributes, 'preference_scope': scope, 'preference_revision': rt.preference_revision,
            'preference_paused': rt.preference_paused, 'preference_exited': rt.preference_exited,
            'attribute_saved': 'attribute' in rt.preferences, 'overall_saved': 'comparison_overall' in rt.preferences,
            'comparison_complete': done and not rt.preference_exited,
            'preferences': deepcopy(rt.preferences)}


def validate_preference(value):
    if not isinstance(value, dict) or set(value) - {'choice_kind', 'selected_conditions', 'comment', 'comment_confirmed'}:
        raise APIError(400, 'invalid_preference', 'Use explicit preference choices and confirmed text only.')
    kind = value.get('choice_kind'); selected = value.get('selected_conditions')
    if not isinstance(kind, str) or kind not in ('selected', 'no_clear_preference', 'none_acceptable', 'unable_to_compare'):
        raise APIError(400, 'invalid_preference', 'Choose a preference or an explicit comparison category.')
    if not isinstance(selected, list) or any(not isinstance(c, str) or c not in CONDITIONS for c in selected) or len(set(selected)) != len(selected):
        raise APIError(400, 'invalid_preference', 'Use unique E/A/N/S selections.')
    if kind == 'selected' and not 1 <= len(selected) <= 3 or kind != 'selected' and selected:
        raise APIError(400, 'invalid_preference', 'Select one to three tied approaches, or one exclusive category.')
    comment = text_value(value.get('comment', ''), 'comment', 4000, empty=True)
    if 'comment_confirmed' in value and type(value['comment_confirmed']) is not bool or comment and value.get('comment_confirmed') is not True:
        raise APIError(400, 'unconfirmed_comment', 'Confirm optional spoken text before submission.')
    return {'choice_kind': kind, 'selected_conditions': [c for c in CONDITIONS if c in selected],
            'comment': comment, 'comment_confirmed': bool(comment)}


def submitted_chain(app, rt):
    chain = []; current = rt
    while current is not None:
        if current.series_id != rt.series_id or current.participant_id != rt.participant_id or current.lifecycle != 'submitted' or not current.submission:
            raise APIError(409, 'incomplete_sequence', 'Submit the registered tasks before comparing approaches.')
        chain.append(current)
        current = app.tasks.get(current.previous_task_id) if current.previous_task_id else None
    chain.reverse()
    if len(chain) != rt.sequence_index:
        raise APIError(409, 'incomplete_sequence', 'The comparison history could not be verified.')
    for index, (item, (_, _, expected)) in enumerate(zip(chain, slots(rt.sequence))):
        actual = {k: getattr(item.comparison, k) for k in ('domain', 'task_code', 'scenario')}
        if item.sequence_index != index + 1 or actual != expected:
            raise APIError(409, 'incomplete_sequence', 'The comparison history does not match its registered sequence.')
    return chain


def preference_command(app, rt, op, data):
    view = sequence_view(rt)
    if not view['registered'] or not view['at_module_end'] or rt.lifecycle != 'submitted' or rt.next_task_id or rt.preference_exited:
        raise APIError(409, 'preference_unavailable', 'Preference feedback is available at a completed attribute boundary.')
    if type(data.get('expected_preference_revision')) is not int or data['expected_preference_revision'] != rt.preference_revision:
        raise APIError(409, 'stale_preference', 'Refresh the current preference step.')
    if op == 'preference':
        if rt.preference_paused or not view['preference_scope'] or data.get('scope') != view['preference_scope']:
            raise APIError(409, 'preference_unavailable', 'Use the current, unpaused preference step.')
        answers = validate_preference(data.get('answers')); chain = submitted_chain(app, rt)
        scope = view['preference_scope']
        if scope == 'comparison_overall':
            boundaries = [x for x in chain if sequence_view(x)['at_module_end']]
            if len(boundaries) != 4 or any('attribute' not in x.preferences for x in boundaries):
                raise APIError(409, 'incomplete_sequence', 'Submit all four attribute preferences first.')
        evidence = chain if scope == 'comparison_overall' else [x for x in chain if x.comparison.domain == rt.comparison.domain]
        record = {'questionnaire_version': VERSION, 'submission_id': uuid.uuid4().hex,
                  'scope': scope, 'domain': rt.comparison.domain if scope == 'attribute' else None,
                  'series_id': rt.series_id, 'module_index': view['module_index'] if scope == 'attribute' else None,
                  'submitted_at_utc': datetime.now(timezone.utc).isoformat(), 'answers': answers,
                  'evaluated_tasks': [{'task_id': x.comparison.task_id, 'task_code': x.comparison.task_code,
                     'domain': x.comparison.domain, 'submission_id': x.submission['submission_id'],
                     'conditions': list(CONDITIONS)} for x in evidence]}
        app._log(rt, 'strategy_preference_submitted', request_id=data['request_id'], preference=record)
        rt.preferences[scope] = record
    elif op == 'preference_pause':
        if rt.preference_paused or view['comparison_complete']:
            raise APIError(409, 'preference_unavailable', 'This preference step cannot be paused.')
        app._log(rt, 'preference_paused', request_id=data['request_id']); rt.preference_paused = True
    elif op == 'preference_resume':
        if not rt.preference_paused:
            raise APIError(409, 'preference_unavailable', 'The preference step is not paused.')
        app._log(rt, 'preference_resumed', request_id=data['request_id']); rt.preference_paused = False
    elif op == 'preference_exit':
        app._log(rt, 'preference_exited', request_id=data['request_id']); rt.preference_exited = True
    rt.preference_revision += 1
