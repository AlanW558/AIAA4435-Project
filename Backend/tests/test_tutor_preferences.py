"""Attribute boundary preferences, evidence scope, retries and isolated STT."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
from core import APIError
from tutor_comparison_service import TutorComparisons
from tutor_preferences import validate_preference, validate_sequence, VERSION
from tutor_feedback import ATTRIBUTE_VERSION, ATTRIBUTE_RATINGS
from tutor_transcription import TutorTranscription
from tutor_dialogue_log import export_rows
from test_tutor_generation import GenerationFixture
from test_tutor_interpretation import tailoring
from test_tutor_transcription import FakeSpeech
from test_speech import wav_bytes


def sequence(domains=('speech_rate', 'reply_length', 'tone', 'voice'), count=1):
    return {'version': 'attribute-sequence-v1', 'purpose': 'practice', 'modules': [
        {'domain': domain, 'tasks': [{'task_code': f'{domain}_{i}', 'scenario': 'C1'} for i in range(count)]} for domain in domains]}


def choice(kind='selected', selected=None):
    return {'choice_kind': kind, 'selected_conditions': (['S'] if selected is None else selected) if kind == 'selected' else []}


class PreferenceValidation(unittest.TestCase):
    def test_ties_and_special_categories(self):
        self.assertEqual(validate_preference(choice(selected=['S','E']))['selected_conditions'], ['E','S'])
        for kind in ('no_clear_preference','none_acceptable','unable_to_compare'):
            self.assertEqual(validate_preference(choice(kind))['choice_kind'], kind)
        for value in [{}, choice(selected=[]), choice(selected=list('EANS')), choice(selected=['E','E']), choice(selected=['X']), {'choice_kind':'no_clear_preference','selected_conditions':['S']}]:
            with self.assertRaises(APIError): validate_preference(value)

    def test_only_confirmed_comment_text(self):
        v = choice(); v['comment'] = 'Reason'
        with self.assertRaises(APIError): validate_preference(v)
        v['comment_confirmed'] = True
        self.assertEqual(validate_preference(v)['comment'], 'Reason')
        v['audio_base64'] = 'raw'
        with self.assertRaises(APIError): validate_preference(v)

    def test_sequence_is_metadata_only_and_practice_only(self):
        self.assertEqual(validate_sequence(sequence()),sequence())
        for change in ('instructions','natural','duplicate','formal'):
            v=sequence()
            if change=='instructions': v['modules'][0]['tasks'][0]['instructions']='PRIVATE GOAL'
            if change=='natural': v['modules'][0]['domain']='natural_scenario'
            if change=='duplicate': v['modules'][1]['tasks'][0]['task_code']=v['modules'][0]['tasks'][0]['task_code']
            if change=='formal': v['purpose']='formal'
            with self.assertRaises(APIError): validate_sequence(v)


class Preferences(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.model=GenerationFixture(); self.model.raw=tailoring('brief')
        self.app=TutorComparisons(self.model,self.temp.name); self.plan=sequence(); self.create()
    def tearDown(self): self.app.shutdown(); self.temp.cleanup()
    def create(self):
        first=self.plan['modules'][0]
        self.id=self.app.create({'request_id':uuid.uuid4().hex,'feedback_version':ATTRIBUTE_VERSION,'sequence':self.plan,'domain':first['domain'],**first['tasks'][0]})['task_id']
    def view(self): return self.app.view(self.app.get(self.id))
    def mutate(self,op,c=None,**payload):
        v=self.view(); rev=v['revision'] if c is None else v['branches'][c]['branch_revision']
        return self.app.mutate(self.id,op,{'request_id':uuid.uuid4().hex, 'expected_revision' if c is None else 'expected_branch_revision':rev,**payload},c)
    def wait(self,predicate):
        until=time.monotonic()+5
        while time.monotonic()<until:
            v=self.view()
            if predicate(v): return v
            time.sleep(.005)
        self.fail('Comparison did not settle')
    def submit_task(self):
        self.mutate('start',query='Use brief answers.')
        v=self.wait(lambda v: all(b['status']!='processing' for b in v['branches'].values()))
        for c in 'EANS':
            if v['branches'][c]['status']=='awaiting_clarification':
                self.mutate('answer',c,question_id=v['branches'][c]['question']['question_id'],response={'option_id':'c1'})
        self.wait(lambda v:v['results_visible'])
        for c in 'EANS': self.mutate('feedback',c,expected_feedback_revision=0,answers={'completion':'fully_met','ratings':{k:5 for k in ATTRIBUTE_RATINGS}})
        self.mutate('submit')
    def pref(self,answers=None,scope=None,rid=None):
        v=self.view(); body={'request_id':rid or uuid.uuid4().hex,'expected_revision':v['revision'],'expected_preference_revision':v['sequence']['preference_revision'],'scope':scope or v['sequence']['preference_scope'],'answers':answers or choice()}
        return self.app.mutate(self.id,'preference',body),body
    def advance(self,mi,ti=0):
        m=self.plan['modules'][mi];v=self.mutate('next',next_task={'domain':m['domain'],**m['tasks'][ti]});self.id=v['next_task_id'];return self.view()
    def lifecycle(self,op): return self.mutate(op,expected_preference_revision=self.view()['sequence']['preference_revision'])
    def logs(self): return [json.loads(l) for p in self.app.log_dir.glob('*.jsonl') for l in p.read_text().splitlines()]

    def test_preference_requires_submitted_boundary_and_next_requires_preference(self):
        with self.assertRaises(APIError): self.pref()
        self.submit_task()
        with self.assertRaises(APIError): self.advance(1)
        with self.assertRaises(APIError): self.pref(scope='comparison_overall')
        self.pref();v=self.advance(1)
        self.assertEqual(v['sequence']['module_index'],1);self.assertEqual(v['sequence_index'],2)
        self.assertEqual(v['baseline']['conversation'],[])

    def test_one_preference_per_module_and_overall_requires_four(self):
        for i in range(4):
            self.submit_task(); self.assertEqual(self.view()['sequence']['preference_scope'],'attribute')
            self.pref(choice('unable_to_compare') if i==1 else choice(selected=['E','S']))
            if i<3: self.advance(i+1)
        self.assertEqual(self.view()['sequence']['preference_scope'],'comparison_overall')
        self.pref(choice('none_acceptable'))
        self.assertTrue(self.view()['sequence']['comparison_complete'])
        with self.assertRaises(APIError): self.pref()
        with self.assertRaises(APIError): self.advance(0)
        prefs=[r['preference'] for r in self.logs() if r['event']=='strategy_preference_submitted']
        self.assertEqual(len(prefs),5)
        overall=next(p for p in prefs if p['scope']=='comparison_overall')
        self.assertEqual(len(overall['evaluated_tasks']),4);self.assertIsNone(overall['domain'])
        self.assertEqual(overall['questionnaire_version'],VERSION)
        rows=list(export_rows(enumerate(self.logs(),1)));self.assertEqual(len([r for r in rows if r['kind']=='strategy_preference']),5)

    def test_in_module_skip_and_premature_overall_rejected(self):
        self.plan=sequence(count=2);self.create();self.submit_task()
        with self.assertRaises(APIError): self.pref()
        with self.assertRaises(APIError): self.advance(1)
        self.advance(0,1);self.submit_task();self.pref()
        with self.assertRaises(APIError): self.pref(scope='comparison_overall')
        v=self.advance(1);self.assertEqual(v['sequence_index'],3)
        boundary=[r['preference'] for r in self.logs() if r['event']=='strategy_preference_submitted'][0]
        self.assertEqual(len(boundary['evaluated_tasks']),2)

    def test_partial_practice_has_no_overall_four_attribute_preference(self):
        self.plan=sequence(('tone',));self.create();self.submit_task();self.pref()
        self.assertTrue(self.view()['sequence']['comparison_complete']);self.assertFalse(self.view()['sequence']['all_attributes'])
        self.assertEqual(self.view()['sequence']['preference_scope'],'')

    def test_lost_ack_replay_immutable_submission_and_audit_failure(self):
        self.submit_task();v,body=self.pref()
        before=len([x for x in self.logs() if x['event']=='strategy_preference_submitted'])
        replay=self.app.mutate(self.id,'preference',body)
        self.assertTrue(replay['idempotent_replay']);self.assertEqual(replay['sequence'],v['sequence'])
        self.assertEqual(before,len([x for x in self.logs() if x['event']=='strategy_preference_submitted']))
        changed=deepcopy(body);changed['answers']=choice('no_clear_preference')
        with self.assertRaises(APIError): self.app.mutate(self.id,'preference',changed)
        self.advance(1);self.submit_task()
        original=self.app._log
        def writer(rt,event,**kwargs):
            if event=='strategy_preference_submitted': raise OSError('fixture')
            original(rt,event,**kwargs)
        with patch.object(self.app,'_log',writer):
            with self.assertRaises(APIError): self.pref()
        self.assertFalse(self.view()['sequence']['attribute_saved'])
        self.pref();self.assertTrue(self.view()['sequence']['attribute_saved'])

    def test_preference_pause_resume_exit_do_not_fabricate_answers(self):
        self.submit_task();self.lifecycle('preference_pause')
        with self.assertRaises(APIError): self.pref()
        with self.assertRaises(APIError): self.advance(1)
        self.lifecycle('preference_resume');self.lifecycle('preference_exit')
        with self.assertRaises(APIError): self.pref()
        self.assertEqual(self.view()['sequence']['preferences'],{})
        self.assertEqual(self.view()['lifecycle'],'submitted')

    def test_preference_stt_isolated_and_invalidated_by_pause_or_submit(self):
        self.submit_task();fake=FakeSpeech();fake.text='PREFERENCE ONLY';gateway=TutorTranscription(None,self.app,fake)
        def body(): return {'request_id':uuid.uuid4().hex,'condition':self.view()['sequence']['preference_scope'],'expected_revision':self.view()['sequence']['preference_revision'],'question_id':'','audio_base64':base64.b64encode(wav_bytes()).decode()}
        data=body(); result=gateway.transcribe('preference',self.id,data)
        self.assertEqual(result,gateway.transcribe('preference',self.id,data));self.assertEqual(fake.calls,1)
        self.assertNotIn(fake.text,json.dumps(self.logs()));self.assertNotIn(data['audio_base64'],repr(gateway.entries))
        a=choice();a.update(comment=result['text'],comment_confirmed=True);self.pref(a)
        with self.assertRaises(APIError): gateway.transcribe('preference',self.id,data)
        self.assertNotIn(fake.text,json.dumps(self.view()['branches']))
        self.advance(1);self.submit_task();fake.hook=lambda:self.lifecycle('preference_pause')
        with self.assertRaises(APIError): gateway.transcribe('preference',self.id,body())
