"""Replay actual malformed outputs without model calls or fabricated outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from model import ModelError
from tutor_interpretation import TutorInterpreter, normalize_interpretation, build_context
from tutor_policy import selective_decision
from tutor_session import TutorSessions
from tutor_state import TutorState

CASES = json.loads((Path(__file__).parent / 'fixtures/tutor_model_shape_recovery.json').read_text())['records']


class Model:
    mode, model = 'fixture', 'shape-recovery-fixture'

    def __init__(self, raw, resolved=None):
        self.raw, self.resolved, self.calls, self.contexts = raw, resolved, [], []

    def interpret_tutor(self, context):
        self.calls.append('interpret'); self.contexts.append(deepcopy(context))
        return deepcopy(self.raw), [{'role': 'tutor_interpreter', 'status': 'fixture'}]

    def resolve_tutor_answer(self, context):
        self.calls.append('resolve'); self.contexts.append(deepcopy(context))
        return deepcopy(self.resolved), [{'role': 'tutor_clarification', 'status': 'fixture'}]


def tone_request(tone, preserved=()):
    raw = deepcopy(CASES['T3-1']['response'])
    raw['proposal']['candidates'][0]['patch'] = {'tone': tone}
    raw['preserved_fields'] = list(preserved)
    return raw


class ModelShapeRecoveryTests(unittest.TestCase):
    def test_exact_supplied_preference_object_is_representation_only(self):
        case = deepcopy(CASES['R4-3'])
        before = deepcopy(case)
        result = normalize_interpretation(case['response'], case['context'])
        self.assertEqual(result['proposal']['possible_soft_preference_overrides'], ['I usually prefer a pace of 1.10.'])
        self.assertEqual(result['proposal']['candidates'][0]['patch'], {'speech_rate': .9})
        self.assertEqual(selective_decision(result['proposal'], case['context']['settings'], case['context']['soft_preferences'])[0], 'ASK')
        self.assertEqual(case, before)

    def test_unknown_preference_object_and_reference_objects_still_rejected(self):
        for kind in ('different_value', 'extra_key', 'no_supplied_preference', 'reference_object'):
            case = deepcopy(CASES['R4-3'])
            item = case['response']['proposal']['possible_soft_preference_overrides'][0]
            if kind == 'different_value': item['value'] = .7
            elif kind == 'extra_key': item['invented'] = 'content'
            elif kind == 'no_supplied_preference': case['context']['soft_preferences'] = []
            else: case['response']['proposal']['unresolved_references'] = [item]
            with self.subTest(kind=kind), self.assertRaises(ModelError):
                normalize_interpretation(case['response'], case['context'])

    def test_bound_restatement_is_resolved_without_applying_misclassified_patch(self):
        case = CASES['T3-1']; state = TutorState(case['context']['settings'])
        model = Model(case['response']); interpreter = TutorInterpreter(model)
        result = interpreter.interpret(case['query'], state.snapshot(), pending=case['context']['pending'], answering_pending_question=True)
        self.assertEqual(result['interpretation']['kind'], 'clarification')
        self.assertEqual(result['interpretation']['clarification'], {'option_id': 'other', 'free_text': case['query']})
        self.assertIsNone(result['interpretation']['proposal'])
        self.assertTrue(model.contexts[0]['answering_pending_question'])
        self.assertEqual(state.snapshot()['settings'], case['context']['settings'])
        unbound = interpreter.interpret(case['query'], state.snapshot(), pending=case['context']['pending'])
        self.assertEqual(unbound['interpretation']['kind'], 'tailoring')

    def test_bound_malformed_patch_is_not_accepted_and_question_is_required(self):
        case = deepcopy(CASES['T3-1']); state = TutorState(case['context']['settings'])
        case['response']['proposal']['candidates'][0]['patch']['tone'] = 'invalid-tone'
        model = Model(case['response'])
        with self.assertRaises(ModelError):
            TutorInterpreter(model).interpret(case['query'], state.snapshot(), pending=case['context']['pending'], answering_pending_question=True)
        with self.assertRaises(APIError):
            build_context(case['query'], state.snapshot(), answering_pending_question=True)

    def test_extra_constraint_uses_full_utterance_not_option_or_truncated_fragment(self):
        case = deepcopy(CASES['T3-2'])
        result = normalize_interpretation(case['response'], case['context'])
        self.assertEqual(result['clarification'], {'option_id': 'other', 'free_text': case['query']})
        self.assertEqual(case['response']['clarification']['option_id'], 'c1')
        for invalid in ('unknown', 'cancel'):
            case['response']['clarification']['option_id'] = invalid
            with self.assertRaises(ModelError): normalize_interpretation(case['response'], case['context'])

    def test_original_failed_clarifications_complete_through_existing_resolver(self):
        for code, tone, preserved in (('T3-1', 'friendly', ['speech_rate', 'voice']), ('T3-2', 'encouraging', ['reply_length'])):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                case = CASES[code]
                model = Model(tone_request(tone), tone_request(tone, preserved))
                sessions = TutorSessions(model, folder)
                view = sessions.create({'condition': 'A', 'settings': case['context']['settings']})
                view = sessions.mutate(view['session_id'], 'request', {'request_id': 'original', 'expected_revision': view['revision'], 'query': case['context']['pending']['original_query']})
                self.assertEqual(view['decision'], 'ASK')
                model.raw = case['response']
                view = sessions.mutate(view['session_id'], 'request', {'request_id': 'answer', 'expected_revision': view['revision'],
                    'question_id': view['question']['question_id'], 'query': case['query']})
                self.assertEqual(view['decision'], 'ACT')
                expected = {**case['context']['settings'], 'tone': tone}
                self.assertEqual(view['settings'], expected)
                self.assertIsNone(view['question'])
                self.assertEqual(model.calls, ['interpret', 'interpret', 'resolve'])
                self.assertEqual(model.contexts[-1]['clarification_resolution']['answer'], case['query'])
                events = [json.loads(line) for line in (sessions.log_dir / (view['session_id'] + '.jsonl')).read_text().splitlines()]
                self.assertEqual(sum(e['event'] == 'gate_decision' for e in events), 1)

    def test_public_context_has_only_catalog_gender_facts(self):
        context = build_context('Use a male voice.', TutorState().snapshot())
        info = context['capabilities']['voice_descriptions']
        self.assertEqual({v for v, d in info.items() if d['catalog_gender'] == 'male'}, {'voice_d', 'voice_e'})
        self.assertEqual({v for v, d in info.items() if d['catalog_gender'] == 'female'}, {'voice_a', 'voice_b', 'voice_c'})
        self.assertIn('longanhuan_v3.6', info['voice_b']['source'])
        self.assertTrue(all(set(d) == {'catalog_gender', 'source'} for d in info.values()))

    def test_required_keep_duplicates_are_canonicalized_without_changing_effect(self):
        for code, expected_patch in (('R3-2', {'speech_rate': .8}), ('L3-2', {'reply_length': 'detailed'})):
            with self.subTest(code=code):
                case = deepcopy(CASES[code]); before = deepcopy(case)
                raw = case['response']
                self.assertTrue(set(raw['required_fields']) & set(raw['preserved_fields']))
                result = normalize_interpretation(raw, case['context'])
                self.assertEqual(result['required_fields'], result['requested_fields'])
                self.assertEqual(result['preserved_fields'], raw['preserved_fields'])
                self.assertEqual(result['proposal']['candidates'][0]['patch'], expected_patch)
                self.assertEqual(case, before)
                model = Model(None, raw)
                context = case['context']; resolution = context['clarification_resolution']
                resolved = TutorInterpreter(model).resolve_answer(case['query'], TutorState(context['settings']).snapshot(),
                    preferences=context['soft_preferences'], pending=resolution['question'], scope=resolution['original_scope'],
                    preserved_fields=resolution['preserved_fields'])
                self.assertEqual(resolved['interpretation'], result)

    def test_required_keep_normalization_never_weakens_constraints(self):
        for kind in ('contradictory_patch', 'unknown_required', 'unrequested_required', 'duplicate_required', 'requested_keep_overlap_without_explicit_value', 'missing_actual_requirement'):
            with self.subTest(kind=kind):
                case = deepcopy(CASES['R3-2']); raw = case['response']
                if kind == 'contradictory_patch': raw['proposal']['candidates'][0]['patch']['tone'] = 'friendly'
                elif kind == 'unknown_required': raw['required_fields'].append('unknown')
                elif kind == 'unrequested_required': raw['required_fields'].append('jacket_color')
                elif kind == 'duplicate_required': raw['required_fields'].append('speech_rate')
                elif kind == 'requested_keep_overlap_without_explicit_value':
                    raw['requested_fields'].append('tone')
                    del raw['proposal']['candidates'][0]['patch']['tone']
                else: del raw['proposal']['candidates'][0]['patch']['speech_rate']
                with self.assertRaises(ModelError): normalize_interpretation(raw, case['context'])


if __name__ == '__main__':
    unittest.main()
