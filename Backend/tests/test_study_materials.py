"""Fixed 32-task catalog, public/private separation and listening access boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError
from tutor_study_materials import CATALOG, DIGEST, VERSION, TASKS
from tutor_preferences import validate_sequence
from tutor_feedback import ATTRIBUTE_RATINGS, ATTRIBUTE_VERSION
from tutor_comparison_service import TutorComparisons
from tutor_audio import TutorAudio
from tutor_state import DEFAULT_SETTINGS
from test_tutor_audio import FakeTTS
from unity_comparison_fixture_server import ComparisonFixture


def plan(first=None):
    modules=[{'domain':m['direction'],'tasks':[{'task_code':t['task_code'],'scenario':t['scenario']} for t in m['tasks']]} for m in CATALOG['modules']]
    if first: modules.sort(key=lambda m:m['domain']!=first)
    return {'version':'attribute-sequence-v2','purpose':'study_preview','materials_version':VERSION,'catalog_sha256':DIGEST,'modules':modules}


class StudyMaterialsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.model=ComparisonFixture();self.app=TutorComparisons(self.model,self.temp.name)
        self.tts=FakeTTS();self.audio=TutorAudio(None,self.app,self.tts)
    def tearDown(self):self.app.shutdown();self.temp.cleanup()
    def create(self,code='R1-1',**overrides):
        domain,t=TASKS[code];p=plan(domain);flat=[(m['domain'],t) for m in p['modules'] for t in m['tasks']];index=next(i for i,(_,t) in enumerate(flat) if t['task_code']==code)
        data={'request_id':uuid.uuid4().hex,'domain':domain,'task_code':code,'scenario':t['scenario'],'feedback_version':ATTRIBUTE_VERSION,'sequence':p,'require_preparation':True,**overrides}
        # Non-first materials are exercised via the internal constructor here;
        # the full walk below uses only ordinary create/next operations.
        self.id=self.app.create(data,lineage=('MATERIAL_TEST',index+1,'') if index else None)['task_id']
        return self.view()
    def view(self):return self.app.view(self.app.get(self.id))
    def mutate(self,op,c=None,**kw):
        v=self.view();return self.app.mutate(self.id,op,{'request_id':uuid.uuid4().hex,'expected_revision' if c is None else 'expected_branch_revision':v['revision'] if c is None else v['branches'][c]['branch_revision'],**kw},c)
    def wait(self,fn):
        end=time.monotonic()+5
        while time.monotonic()<end:
            v=self.view()
            if fn(v):return v
            time.sleep(.005)
        self.fail('Fixture did not settle')
    def audio_body(self,index=1):
        v=self.view();return dict(request_id=uuid.uuid4().hex,condition=v['selected_condition'],purpose='material',exchange_id=index,expected_revision=v['revision'])
    def test_catalog_matches_selected_32_ids_and_scenarios(self):
        expected={'R1-1','R1-2','R2-1','R2-2','R3-1','R3-2','R4-1','R4-3','L1-1','L1-3','L2-1','L2-2','L3-1','L3-2','L4-2','L4-3','T1-1','T1-3','T2-2','T2-3','T3-1','T3-2','T4-1','T4-3','V1-1','V1-2','V2-1','V2-2','V3-1','V3-2','V4-2','V4-3'}
        self.assertEqual(set(TASKS),expected)
        for m in CATALOG['modules']:
            self.assertEqual(len(m['tasks']),8)
            for c in ('C1','C2','C3','C4'):self.assertEqual(sum(t['scenario']==c for t in m['tasks']),2)
    def test_catalog_identity_and_private_field_rejection(self):
        for mut in (lambda p:p.update(catalog_sha256='0'*64),lambda p:p.update(materials_version='old'),lambda p:p['modules'][0]['tasks'].pop(),lambda p:p['modules'][0]['tasks'][0].update(instructions='PRIVATE'),lambda p:p.update(purpose='formal')):
            p=plan();mut(p)
            with self.assertRaises(APIError):validate_sequence(p)
        self.assertEqual(validate_sequence(plan('voice')),plan('voice'))
    def test_all_baselines_are_fixed_identical_and_private_cards_absent(self):
        for code,(domain,t) in TASKS.items():
            v=self.create(code);baseline=v['baseline']
            self.assertTrue(v['preparation_locked']);self.assertTrue(v['preparation_required']);self.assertIsNone(v['initial_query'])
            for rb in self.app.get(self.id).branches.values():self.assertEqual(rb.session.state.snapshot(),baseline)
            self.assertNotIn(t['instructions'],json.dumps(v))
            with self.assertRaises(APIError) as cm:self.mutate('prepare',patch={'speech_rate':1.05})
            self.assertEqual(cm.exception.code,'fixed_study_baseline')
            self.mutate('confirm_preparation');self.assertEqual(self.view()['baseline'],baseline)
            self.assertEqual(baseline['settings']['voice'],t['public_start']['public_setup'][-2].get('patch',{}).get('voice',t['public_start']['settings']['voice']) if len(t['public_start']['public_setup'])>1 else t['public_start']['settings']['voice'])
    def test_overrides_and_collection_phase_rejected(self):
        for value in ({'settings':{}},{'public_setup':[]},{'soft_preferences':[]},{'require_preparation':False},{'phase':'study'}):
            with self.assertRaises(APIError):self.create(**value)
        self.assertFalse(self.app.tasks)
    def test_numeric_reference_baselines_and_partial_restore_history(self):
        for code in ('R1-1','R1-2'):self.assertEqual(self.create(code)['baseline']['settings']['speech_rate'],1.2)
        self.assertEqual(self.create('R4-1')['baseline']['changes'][0]['before']['speech_rate'],.9)
        v=self.create('L4-3');self.assertEqual(v['baseline']['settings']['tone'],'friendly');self.assertEqual(v['baseline']['changes'][0]['before']['reply_length'],'balanced')
        v=self.create('V4-3');self.assertEqual(v['baseline']['settings']['speech_rate'],1.15);self.assertEqual(v['baseline']['settings']['tone'],'friendly')
    def test_public_preferences_not_private_targets(self):
        for code,field,value in [('R4-3','speech_rate',1.1),('T4-3','tone','professional')]:
            self.create(code)
            for b in self.app.get(self.id).branches.values():self.assertEqual(b.session.preferences[0]['value'],value)
            logs='\n'.join(p.read_text() for p in Path(self.temp.name).rglob('*.jsonl'))
            self.assertNotIn(TASKS[code][1]['instructions'],logs)
    def test_voice_materials_are_authoritative_and_do_not_mutate_dialogue(self):
        for code in (c for c in TASKS if c.startswith('V')):
            v=self.create(code);before=deepcopy(v['baseline'])
            for index,item in enumerate(TASKS[code][1]['materials'],1):
                self.audio.synthesize('comparisons',self.id,self.audio_body(index))
                self.assertEqual(self.tts.calls[-1],(item['text'],{**DEFAULT_SETTINGS,**item['settings']}))
            self.assertEqual(self.view()['baseline'],before);self.assertEqual(self.model.calls,[])
            with self.assertRaises(APIError):self.audio.synthesize('comparisons',self.id,self.audio_body(99))
    def test_material_audio_hidden_during_clarification(self):
        self.create('V1-1');self.mutate('confirm_preparation');self.mutate('start',query='Compare an easier explanation.')
        self.wait(lambda v:all(b['status']!='processing' for b in v['branches'].values()))
        with self.assertRaises(APIError) as cm:self.audio.synthesize('comparisons',self.id,self.audio_body())
        self.assertEqual(cm.exception.code,'audio_hidden');self.assertFalse(self.tts.calls)
    def test_material_audio_pause_and_late_return(self):
        self.create('V1-1');self.tts.hook=lambda:self.mutate('pause')
        with self.assertRaises(APIError):self.audio.synthesize('comparisons',self.id,self.audio_body())
        logs='\n'.join(p.read_text() for p in Path(self.temp.name).rglob('*.jsonl'))
        self.assertIn('audio_discarded',logs);self.assertNotIn('audio_ready',logs)
    def test_complete_registered_32_task_sequence_and_five_preferences(self):
        self.create();p=plan();flat=[{'domain':m['domain'],**t} for m in p['modules'] for t in m['tasks']]
        ids=[];preference_count=0
        for i,spec in enumerate(flat):
            self.assertEqual(self.view()['task_code'],spec['task_code']);self.assertEqual(self.view()['sequence_index'],i+1)
            ids.append(self.id);self.mutate('confirm_preparation');self.mutate('start',query='Compare an easier explanation.')
            self.wait(lambda v:all(b['status']!='processing' for b in v['branches'].values()))
            for c in 'EANS':
                b=self.view()['branches'][c]
                if b['status']=='awaiting_clarification':
                    self.mutate('answer',c,question_id=b['question']['question_id'],response={'option_id':'c1'})
            self.wait(lambda v:v['results_visible'])
            for c in 'EANS':self.mutate('feedback',c,expected_feedback_revision=0,answers={'completion':'fully_met','ratings':{k:5 for k in ATTRIBUTE_RATINGS}})
            self.mutate('submit')
            while self.view()['sequence']['preference_scope']:
                v=self.view();self.mutate('preference',scope=v['sequence']['preference_scope'],expected_preference_revision=v['sequence']['preference_revision'],answers={'choice_kind':'no_clear_preference','selected_conditions':[]});preference_count+=1
            if i<31:
                response=self.mutate('next',next_task=flat[i+1]);self.id=response['next_task_id']
        self.assertEqual(len(set(ids)),32);self.assertEqual(preference_count,5);self.assertTrue(self.view()['sequence']['comparison_complete'])
        record=self.view()['sequence']['preferences']['comparison_overall'];self.assertEqual(len(record['evaluated_tasks']),32)
        for m in self.model.calls:
            raw=json.dumps(m)
            for _,task in TASKS.values():self.assertNotIn(task['instructions'],raw)


if __name__=='__main__':unittest.main()
