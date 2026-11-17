"""Actual comparison/session execution -> new questionnaires -> durable export."""
import json
from pathlib import Path
import tempfile
import time
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Experiment, APIError
from server import Server
from test_tutor_generation import GenerationFixture
from test_tutor_interpretation import tailoring
from test_tutor_session import chat
from test_study_store import Fixture, answers
from study_store import uid
from export_study_data import export_run


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.model=GenerationFixture()
        self.server=Server(('127.0.0.1',0),Experiment(self.model,self.tmp.name))
        self.f=Fixture(Path(self.tmp.name)/'study');self.f.store=self.server.study
        self.mid=self.f.module();self.tid=self.f.send('open_task',{'module_instance_id':self.mid,'task_code':self.f.state['manifest']['tasks'][0]['task_code']})['task_id']
        self.rid=self.f.send('launch_runtime',{'target_id':self.tid})['runtime_id']
    def tearDown(self):self.server.server_close();self.tmp.cleanup()
    def view(self):return self.server.comparisons.view(self.server.comparisons.get(self.rid))
    def action(self,op,c=None,**fields):
        v=self.view();key='expected_branch_revision' if c else 'expected_revision'
        data={'request_id':uid(),key:v['branches'][c]['branch_revision'] if c else v['revision'],**fields}
        qualified=op+(':'+c if c else '')
        self.server.study_flow.before(self.rid,qualified,data)
        result=self.server.comparisons.mutate(self.rid,op,data,condition=c)
        self.server.study_flow.after(self.rid,qualified,data,{'status':202,'body':result})
        return result
    def settle(self):
        until=time.monotonic()+5
        while time.monotonic()<until:
            if all(b['status'] not in ('processing','idle') for b in self.view()['branches'].values()):
                self.server.study_flow.checkpoint(self.rid);return self.view()
            time.sleep(.005)
        self.fail('Runtime did not settle')
    def revealed(self):
        self.action('confirm_preparation');self.model.raw=tailoring('brief',kind='mixed',conversation_query='What is recall?')
        self.action('start',query='Please give only the key points. What is recall?');v=self.settle()
        self.assertFalse(v['results_visible'])
        with self.assertRaises(APIError):self.f.send('capture_evaluation',{'task_id':self.tid})
        for c in 'EANS':
            q=self.view()['branches'][c].get('question')
            if q:self.action('answer',c,question_id=q['question_id'],response={'option_id':'c1'})
        self.settle();self.assertTrue(self.view()['results_visible'])
    def finish_attributes(self):
        self.revealed();self.f.send('capture_evaluation',{'task_id':self.tid})
        for c in 'EANS':self.f.feedback(self.mid,self.tid,c)
        self.f.submit(self.tid);self.f.pref();self.f.pref(None)
    def test_real_results_new_feedback_dialogue_export(self):
        self.finish_attributes()
        output=Path(self.tmp.name)/'export';manifest=export_run(self.f.store,self.f.run,output)
        self.assertEqual(manifest['counts']['attribute_feedback'],4)
        dialogue=[json.loads(l) for l in (output/'dialogue.jsonl').read_text().splitlines()]
        self.assertTrue(any(x.get('kind')=='request' and 'key points' in x.get('text','') for x in dialogue))
        self.assertTrue(any(x.get('kind')=='answer' for x in dialogue))
        with self.assertRaises(APIError):self.action('settings','S',patch={'tone':'friendly'})
    def test_ready_runtime_restores_without_provider_calls(self):
        self.revealed();old=self.view();self.server.server_close()
        self.server=Server(('127.0.0.1',0),Experiment(self.model,self.tmp.name));self.f.store=self.server.study
        restored=self.view();self.assertEqual(restored['task_id'],old['task_id']);self.assertEqual(restored['first_reveal'],old['first_reveal'])
        self.f.send('capture_evaluation',{'task_id':self.tid})
    def test_client_snapshot_omits_only_submitted_result_bodies(self):
        self.revealed();self.f.send('capture_evaluation',{'task_id':self.tid})
        full=self.f.store.read(self.f.run);slim=self.f.store.client_snapshot(self.f.run)
        self.assertEqual(slim,full)
        for c in 'EANS':self.f.feedback(self.mid,self.tid,c)
        self.f.submit(self.tid)
        slim=self.f.store.client_snapshot(self.f.run);full=self.f.store.read(self.f.run)
        self.assertIsNone(slim['tasks'][self.tid]['evaluation'])
        self.assertIsNotNone(full['tasks'][self.tid]['evaluation'])
        for qid,q in full['questionnaires'].items():
            self.assertIn('evaluation_binding',q)
            self.assertNotIn('evaluation_binding',slim['questionnaires'][qid])
            self.assertNotIn('evaluation',slim['questionnaires'][qid])
            self.assertEqual(q['answers'],slim['questionnaires'][qid]['answers'])

    def test_changed_result_requires_new_binding_before_feedback(self):
        self.revealed();self.f.send('capture_evaluation',{'task_id':self.tid})
        self.f.feedback(self.mid,self.tid,'S')
        self.action('settings','S',patch={'tone':'friendly'})
        with self.assertRaises(APIError) as error:self.f.feedback(self.mid,self.tid,'S')
        self.assertEqual(error.exception.code,'stale_evaluation')
        self.f.send('capture_evaluation',{'task_id':self.tid})
        q=next(q for q in self.f.state['questionnaires'].values() if q['condition']=='S')
        self.assertEqual(q['evaluation_status'],'stale')

    def test_runtime_replay_returns_current_revision_without_reapplying(self):
        body={'request_id':uid(),'expected_revision':self.view()['revision']}
        self.server.study_flow.before(self.rid,'confirm_preparation',body)
        result=self.server.comparisons.mutate(self.rid,'confirm_preparation',body)
        self.server.study_flow.after(self.rid,'confirm_preparation',body,{'status':202,'body':result})
        self.action('select',condition='A')
        revision=self.view()['revision']
        replay=self.server.study_flow.before(self.rid,'confirm_preparation',body)
        self.assertTrue(replay['body']['idempotent_replay'])
        self.assertEqual(replay['body']['revision'],revision)
        self.assertEqual(self.view()['revision'],revision)

    def test_survey_transcript_does_not_enter_conversation_or_save_audio(self):
        import base64
        from test_tutor_transcription import FakeSpeech
        from test_speech import wav_bytes
        self.revealed();self.f.send('capture_evaluation',{'task_id':self.tid})
        q=next(q for q in self.f.state['questionnaires'].values() if q['condition']=='S')
        fake=FakeSpeech();fake.text='My optional survey explanation.'
        self.server.transcription.speech=fake
        body={'request_id':uid(),'expected_revision':self.f.state['revision'],'condition':'S',
              'question_id':q['questionnaire_id'],'audio_base64':base64.b64encode(wav_bytes()).decode()}
        before=self.view()
        transcript=self.server.study_flow.transcribe(self.f.run,body)
        self.assertEqual(transcript['text'],fake.text)
        self.server.study_flow.transcribe(self.f.run,body);self.assertEqual(fake.calls,1)
        after=self.view()
        for key in ("revision","branches","first_reveal","phase"):
            self.assertEqual(after[key],before[key])
        state,events=self.f.store.snapshot(self.f.run)
        self.assertNotIn(fake.text,json.dumps([state,events]))
        self.assertNotIn(body['audio_base64'],json.dumps([state,events]))
        self.assertNotIn(body['audio_base64'],repr(self.server.transcription.entries))
        self.f.feedback(self.mid,self.tid,'S')
        with self.assertRaises(APIError):self.server.study_flow.transcribe(self.f.run,body)

    def test_lost_runtime_receipt_recovery_verifies_identity_without_replay(self):
        body={'request_id':uid(),'expected_revision':self.view()['revision']}
        packet={'study_run_id':self.f.run,'runtime_id':self.rid,'operation':'confirm_preparation','body':body}
        with self.assertRaises(APIError) as error:self.server.study_flow.recover_receipt(self.f.run,packet)
        self.assertEqual(error.exception.code,'runtime_receipt_unknown')
        self.server.study_flow.before(self.rid,'confirm_preparation',body)
        result=self.server.comparisons.mutate(self.rid,'confirm_preparation',body)
        self.server.study_flow.after(self.rid,'confirm_preparation',body,{'status':202,'body':result})
        revision=self.view()['revision']
        receipt=self.server.study_flow.recover_receipt(self.f.run,packet)
        self.assertTrue(receipt['recorded']);self.assertFalse(receipt['replay_model_calls'])
        self.assertEqual(self.view()['revision'],revision)
        with self.assertRaises(APIError):self.server.study_flow.recover_receipt(uid(),packet)
        with self.assertRaises(APIError):self.server.study_flow.recover_receipt(self.f.run,{**packet,'operation':'start'})

    def test_unknown_inflight_is_blocked_not_reexecuted(self):
        body={'request_id':uid(),'expected_revision':self.view()['revision'],'query':'unknown request'}
        self.server.study_flow.before(self.rid,'start',body)
        self.server.server_close();self.server=Server(('127.0.0.1',0),Experiment(self.model,self.tmp.name))
        with self.assertRaises(APIError) as error:self.server.study_flow.checkpoint(self.rid)
        self.assertEqual(error.exception.code,'runtime_reconciliation_required')
        self.f.store=self.server.study;self.f.send('end_run',{'end_reason':'technical_abort'})
    def test_natural_real_session_freeze_feedback_end(self):
        self.finish_attributes();mid=self.f.module(None)
        sid=self.f.send('launch_runtime',{'target_id':mid})['runtime_id']
        self.model.raw=chat('Explain recall in one short example.')
        view=self.server.tutor.view(self.server.tutor.get(sid))
        data={'request_id':uid(),'expected_revision':view['revision'],'query':'Explain recall in one short example.'}
        self.server.study_flow.before(sid,'request',data);result=self.server.tutor.mutate(sid,'request',data);self.server.study_flow.after(sid,'request',data,{'status':200,'body':result})
        for job in result['generation_jobs']:
            d={'request_id':uid(),'expected_revision':self.server.tutor.view(self.server.tutor.get(sid))['revision'],'job_id':job['job_id']}
            self.server.study_flow.before(sid,'generate',d);r=self.server.tutor.mutate(sid,'generate',d);self.server.study_flow.after(sid,'generate',d,{'status':200,'body':r})
        self.f.send('finish_natural',{'module_instance_id':mid});self.f.feedback(mid,None)
        self.f.send('submit_natural',{'module_instance_id':mid,'evaluation_revision':1});self.f.send('end_run',{'end_reason':'normal_completion'})
        manifest=export_run(self.f.store,self.f.run,Path(self.tmp.name)/'natural-export')
        self.assertEqual(manifest['counts']['natural_feedback'],1)
        self.assertEqual(self.f.state['end_reason'],'normal_completion')

if __name__=='__main__':unittest.main()
