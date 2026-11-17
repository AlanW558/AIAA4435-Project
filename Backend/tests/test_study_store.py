import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import APIError, Experiment
from model import MockModel
from server import Server
from study_store import StudyStore, PROTOCOL, encoded, uid, digest
from tutor_state import DEFAULT_SETTINGS
from study_answers import ATTRIBUTE_VERSION, NATURAL_VERSION, validate_answers, scores
from export_study_data import export_run


def answers(natural=False):
    if not natural:
        return {'A0': {'status': 'answered', 'value': 'not_met'}, **{f'A{i}': {'status': 'answered', 'value': 5} for i in range(1, 5)}}
    return {'N0': {'status': 'answered', 'value': 'partly_met'},
            **{f'N{i}': {'status': 'answered', 'value': 4} for i in range(1, 8)},
            **{f'S{i}': {'status': 'answered', 'value': 5 if i % 2 else 1} for i in range(1, 11)},
            **{f'U{i}': {'status': 'answered', 'value': 7} for i in range(1, 9)}}


def manifest(full=False):
    tasks = [{'task_code': f'{d}-{c}-{n}', 'domain': d, 'scenario': f'C{c}'}
             for d in (('speech_rate', 'reply_length', 'tone', 'voice') if full else ('speech_rate',))
             for c in (range(1, 5) if full else (1,)) for n in ((1, 2) if full else (1,))]
    return {'protocol_version': PROTOCOL, 'task_manifest_version': 'engineering-fixture-v1',
            'task_manifest_sha256': '1' * 64, 'questionnaire_manifest_sha256': '2' * 64,
            'configuration_sha256': '3' * 64, 'app_build_id': 'test-only', 'backend_build_id': 'test-only', 'tasks': tasks}


class Fixture:
    def __init__(self, folder, full=False):
        self.store = StudyStore(folder); self.run = None
        self.send('create_run', {'participant_id': 'ENG-test', 'collection_kind': 'engineering', 'execution_mode': 'mock', 'manifest': manifest(full)})
    @property
    def state(self): return self.store.read(self.run)
    def packet(self, op, payload):
        return {'request_id': uid(), 'operation': op, 'expected_revision': self.state['revision'] if self.run else 0,
                'study_run_id': self.run, 'payload_json': encoded(payload)}
    def send(self, op, payload):
        ack = self.store.command(self.packet(op, payload))
        if op == 'create_run': self.run = ack['study_run_id']
        return ack['result']
    def module(self, domain='speech_rate'):
        return self.send('open_module', {'module_type': 'natural_selective' if domain is None else 'attribute_comparison', 'domain': domain, **({'initial_state': DEFAULT_SETTINGS} if domain is None else {})})['module_instance_id']
    def task(self, mid, task_code=None):
        code = task_code or self.state['manifest']['tasks'][0]['task_code']
        tid = self.send('open_task', {'module_instance_id': mid, 'task_code': code})['task_id']
        self.bind(tid)
        return tid
    def bind(self, tid):
        revision = self.state['tasks'][tid]['evaluation_revision'] + 1
        self.send('bind_evaluation', {'task_id': tid, 'first_reveal_id': 'first-reveal', 'branches': {c: {'branch_revision': revision, 'state_revision': revision, 'status': 'ready', 'result': {'message': 'synthetic result'}} for c in 'EANS'}})
    def feedback(self, mid, tid, condition='E', data=None):
        natural = tid is None
        obj = self.state['modules'][mid] if natural else self.state['tasks'][tid]
        return self.send('save_feedback', {'module_instance_id': mid, 'task_id': tid, 'condition': 'S' if natural else condition,
                                         'evaluation_revision': obj['evaluation_revision'], 'questionnaire_version': NATURAL_VERSION if natural else ATTRIBUTE_VERSION,
                                         'answers': data if data is not None else answers(natural)})
    def submit(self, tid):
        return self.send('submit_task', {'task_id': tid, 'evaluation_revision': self.state['tasks'][tid]['evaluation_revision']})
    def pref(self, domain='speech_rate'):
        return self.send('preference', {'scope': 'attribute' if domain else 'comparison_overall', 'domain': domain,
                                       'answers': {'choice_kind': 'selected', 'selected_conditions': ['S'], 'comment': '', 'comment_confirmed': False}})
    def natural(self):
        mid = self.module(None)
        self.send('dialogue', {'module_instance_id': mid, 'task_id': None, 'condition': 'S', 'speaker': 'participant', 'kind': 'request',
                              'text': '=I would like a friendly tutor.', 'input_source': 'stt_submitted', 'client_time_utc': '2026-11-16T00:00:00Z', 'client_sequence': 1})
        self.send('freeze_natural', {'module_instance_id': mid, 'final_state': {'tone': 'friendly'}, 'pending_requests': 0, 'end_reason': 'participant_finished'})
        return mid
    def finish_attributes(self):
        tasks = self.state['manifest']['tasks']
        for domain in dict.fromkeys(t['domain'] for t in tasks):
            mid = self.module(domain)
            for spec in [t for t in tasks if t['domain'] == domain]:
                tid = self.task(mid, spec['task_code'])
                for c in 'EANS': self.feedback(mid, tid, c)
                self.submit(tid)
            self.pref(domain)
        self.pref(None)


class Persistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.f = Fixture(self.root / 'data')
    def tearDown(self): self.tmp.cleanup()
    def test_restart_and_lost_ack_exact_receipt(self):
        packet = self.f.packet('open_module', {'module_type': 'attribute_comparison', 'domain': 'speech_rate'})
        ack = self.f.store.command(packet)
        restarted = StudyStore(self.root / 'data')
        replay = restarted.command(packet)
        self.assertEqual({k:v for k,v in replay.items() if k != 'idempotent_replay'}, ack)
        self.assertEqual(len(restarted.read(self.f.run)['modules']), 1)
        packet['payload_json'] = encoded({'module_type': 'attribute_comparison', 'domain': 'voice'})
        with self.assertRaises(APIError) as ctx: restarted.command(packet)
        self.assertEqual(ctx.exception.code, 'request_id_conflict')
    def test_transaction_rolls_back_failure_before_ack(self):
        packet = self.f.packet('open_module', {'module_type': 'attribute_comparison', 'domain': 'speech_rate'})
        with patch.object(self.f.store, '_before_commit', side_effect=sqlite3.OperationalError('simulated full disk')):
            with self.assertRaises(APIError): self.f.store.command(packet)
        self.assertEqual(self.f.state['modules'], {})
        with self.assertRaises(APIError): self.f.store.receipt(packet['request_id'])
        self.assertTrue(self.f.store.command(packet)['recorded'])
    def test_concurrent_same_request_only_one_commit(self):
        packet = self.f.packet('open_module', {'module_type': 'attribute_comparison', 'domain': 'speech_rate'})
        with ThreadPoolExecutor(8) as pool: acks = list(pool.map(lambda _: self.f.store.command(packet), range(8)))
        self.assertEqual(len({a['result']['module_instance_id'] for a in acks}), 1)
        self.assertEqual(sum(e['event']=='open_module' for e in self.f.store.snapshot(self.f.run)[1]), 1)
    def test_final_submission_atomic_all_four_and_restart(self):
        mid = self.f.module(); tid = self.f.task(mid)
        for c in 'EANS': self.f.feedback(mid, tid, c)
        packet = self.f.packet('submit_task', {'task_id': tid, 'evaluation_revision': 1})
        with patch.object(self.f.store, '_before_commit', side_effect=sqlite3.OperationalError()):
            with self.assertRaises(APIError): self.f.store.command(packet)
        self.assertTrue(all(q['record_stage']=='draft' for q in self.f.state['questionnaires'].values()))
        ack = self.f.store.command(packet)
        self.f.store = StudyStore(self.root / 'data')
        self.assertEqual(self.f.store.command(packet)['result']['submission_id'], ack['result']['submission_id'])
        self.assertEqual(len({q['submission_id'] for q in self.f.state['questionnaires'].values()}), 1)
        self.assertTrue(all(q['answers']['A0']['value']=='not_met' for q in self.f.state['questionnaires'].values()))
    def test_drafts_and_stale_feedback_never_export_as_final(self):
        mid = self.f.module(); tid = self.f.task(mid)
        self.f.feedback(mid, tid, data={'A0': {'status': 'unable_to_judge', 'value': None}})
        self.f.bind(tid)
        self.assertEqual(next(iter(self.f.state['questionnaires'].values()))['evaluation_status'], 'stale')
        with self.assertRaises(APIError): self.f.submit(tid)
        self.f.send('end_run', {'end_reason': 'participant_exit'})
        result = export_run(self.f.store, self.f.run, self.root / 'export')
        self.assertEqual(result['counts']['attribute_feedback'], 0)
        self.assertGreater(result['counts']['incomplete_records'], 0)
        with self.assertRaises(APIError): self.f.feedback(mid, tid)
    def test_rebind_invalidates_until_reconfirmed(self):
        mid=self.f.module(); tid=self.f.task(mid)
        for c in 'EANS': self.f.feedback(mid, tid, c)
        self.f.bind(tid)
        with self.assertRaises(APIError): self.f.submit(tid)
        for c in 'EANS': self.f.feedback(mid, tid, c)
        self.f.submit(tid)
        with self.assertRaises(APIError): self.f.bind(tid)
    def test_partial_natural_can_submit_without_inventing_scores(self):
        self.f.finish_attributes(); mid = self.f.natural()
        data = answers(True); data['S4'] = {'status':'skipped','value':None}; data['U8'] = {'status':'skipped','value':None}
        data['N5'] = {'status':'not_applicable','value':None,'reason':'no_clarification_questions'}
        self.f.feedback(mid, None, data=data)
        self.f.send('submit_natural', {'module_instance_id':mid,'evaluation_revision':1})
        self.f.send('end_run', {'end_reason':'normal_completion'})
        result=export_run(self.f.store,self.f.run,self.root/'export')
        with (self.root/'export/natural_feedback.csv').open(encoding='utf-8-sig') as stream: rows=list(csv.DictReader(stream))
        self.assertEqual(rows[0]['completeness'],'partial'); self.assertEqual(rows[0]['sus_value'],'')
        self.assertEqual(rows[0]['ueq_pragmatic_value'],'3.0'); self.assertEqual(rows[0]['ueq_hedonic_value'],'')
        self.assertEqual(rows[0]['N5_status'],'not_applicable')
        self.assertEqual(result['export_status'],'unreconciled')
    def test_full_32_task_128_plus_1_plus_5_export(self):
        f=Fixture(self.root/'full',full=True); f.finish_attributes(); mid=f.natural(); f.feedback(mid,None)
        f.send('submit_natural',{'module_instance_id':mid,'evaluation_revision':1})
        f.send('end_run',{'end_reason':'normal_completion'})
        result=export_run(f.store,f.run,self.root/'full-export')
        self.assertEqual([result['counts'][k] for k in ('attribute_feedback','natural_feedback','preferences')],[128,1,5])
        self.assertEqual(result['counts']['incomplete_records'],0)
        for name, item in result['files'].items():
            import hashlib
            self.assertEqual(hashlib.sha256((self.root/'full-export'/name).read_bytes()).hexdigest(),item['sha256'])
        with self.assertRaises(FileExistsError): export_run(f.store,f.run,self.root/'full-export')
    def test_reconcile_detects_unsent_draft_and_recovers_lost_receipt(self):
        journal=self.root/'journal';journal.mkdir()
        packet=self.f.packet('connect',{'connection_id':uid()})
        ack=self.f.store.command(packet)
        entry={'sequence':1,'kind':'command','scope':self.f.run,'endpoint':'http://127.0.0.1:8765',
               'request_id':packet['request_id'],'payload':encoded(packet),'sha256':digest(encoded(packet))}
        (journal/'00000000000000000001.json').write_text(encoded(entry))
        out=export_run(self.f.store,self.f.run,self.root/'reconciled',journal)
        self.assertEqual(out['synchronization_status'],'provided_copy_reconciled')
        report=json.loads((self.root/'reconciled/local_reconciliation.json').read_text())
        self.assertEqual(report['server_receipts_missing_locally'],[ack['request_id']])
        draft={'sequence':2,'kind':'draft','scope':'draft:'+uid(),'payload':'{"answers":{}}','sha256':digest('{"answers":{}}')}
        (journal/'00000000000000000002.json').write_text(encoded(draft))
        out=export_run(self.f.store,self.f.run,self.root/'unsent-draft',journal)
        self.assertEqual(out['synchronization_status'],'unreconciled')
        draft['sha256']='0'*64;(journal/'00000000000000000002.json').write_text(encoded(draft))
        with self.assertRaises(ValueError):export_run(self.f.store,self.f.run,self.root/'corrupt',journal)
        self.assertFalse((self.root/'corrupt').exists())
    def test_reconciliation_scopes_rejections_to_the_exported_run(self):
        from study_reconcile import reconcile
        journal=self.root/'multi-run-journal';journal.mkdir()
        entries=[]
        def append(kind, rid, payload):
            body=encoded(payload);seq=len(entries)+1
            entry={'sequence':seq,'kind':kind,'request_id':rid,'payload':body,'sha256':digest(body)}
            entries.append(entry);(journal/f'{seq:020d}.json').write_text(encoded(entry))
        packet=self.f.packet('connect',{'connection_id':uid()});self.f.store.command(packet)
        append('command',packet['request_id'],packet)
        other_run=uid()
        for error in ('study_ended','request_id_conflict'):
            old={**self.f.packet('pause',{}),'study_run_id':other_run}
            append('command',old['request_id'],old)
            append('rejection',old['request_id'],{'error':error})
        report=reconcile(self.f.store,self.f.run,self.f.state['revision'],journal)
        self.assertEqual(report['rejected_requests'],[])
        self.assertEqual(report['conflicting_requests'],[])
        self.assertEqual(report['status'],'provided_copy_reconciled')
        current=self.f.packet('pause',{})
        append('command',current['request_id'],current)
        append('rejection',current['request_id'],{'error':'request_id_conflict'})
        report=reconcile(self.f.store,self.f.run,self.f.state['revision'],journal)
        self.assertEqual(report['rejected_requests'],[current['request_id']])
        self.assertEqual(report['conflicting_requests'],[current['request_id']])
        self.assertEqual(report['status'],'unreconciled')

    def test_only_changed_branch_needs_feedback_reconfirmation(self):
        mid=self.f.module();tid=self.f.task(mid)
        for c in 'EANS':self.f.feedback(mid,tid,c)
        p=self.f.state['tasks'][tid]['evaluation']
        p['branches']['S'].update(branch_revision=2,state_revision=2,result={'message':'changed'})
        self.f.send('bind_evaluation',p)
        statuses={q['condition']:q['evaluation_status'] for q in self.f.state['questionnaires'].values()}
        self.assertEqual(statuses,{'E':'current','A':'current','N':'current','S':'stale'})
        self.f.feedback(mid,tid,'S');self.f.submit(tid)
    def test_unsubmitted_and_saved_tasks_remain_distinct_after_exit(self):
        self.f.finish_attributes()
        self.f.send('end_run',{'end_reason':'participant_exit'})
        out=export_run(self.f.store,self.f.run,self.root/'exit')
        self.assertEqual(out['counts']['attribute_feedback'],4)
        self.assertEqual(out['counts']['natural_feedback'],0)
        self.assertEqual(out['backend_record_status'],'partial')

    def test_formal_blocked_and_old_versions_rejected(self):
        p={'participant_id':'ENG-test','collection_kind':'formal','execution_mode':'live','manifest':manifest()}
        body={'request_id':uid(),'operation':'create_run','expected_revision':0,'payload_json':encoded(p)}
        with self.assertRaises(APIError) as ctx: self.f.store.command(body)
        self.assertEqual(ctx.exception.code,'formal_collection_disabled')
        with self.assertRaises(APIError): validate_answers('attribute-feedback-v2',answers())
    def test_identity_registration_replay_and_repeat(self):
        body={'request_id':uid(),'operation':'register_participant','expected_revision':0,'payload_json':encoded({'prior_participation':'yes'})}
        ack=self.f.store.command(body); self.assertEqual(ack['result']['participant_id'],'P0001')
        self.assertEqual(self.f.store.command(body)['result'],ack['result'])
        body['request_id']=uid(); self.assertEqual(self.f.store.command(body)['result']['participant_id'],'P0002')
    def test_pause_requires_resume_and_preserves_run(self):
        self.f.send('pause',{})
        with self.assertRaises(APIError): self.f.module()
        self.f.store=StudyStore(self.root/'data'); self.f.send('resume',{})
        self.assertEqual(self.f.state['lifecycle'],'active')
    def test_subprocess_exit_after_uncommitted_transaction(self):
        before=self.f.state
        script='import sqlite3,os,sys; d=sqlite3.connect(sys.argv[1]); d.execute("BEGIN IMMEDIATE"); d.execute("DELETE FROM runs"); os._exit(17)'
        result=subprocess.run([sys.executable,'-c',script,str(self.f.store.path)],capture_output=True)
        self.assertEqual(result.returncode,17); self.assertEqual(self.f.store.read(self.f.run),before)


class Validation(unittest.TestCase):
    def test_item_ranges_and_statuses(self):
        for item,value in [('A1',True),('A2',0),('A3',8),('A4',4.5)]:
            with self.subTest(item=item):
                a=answers(); a[item]['value']=value
                with self.assertRaises(APIError):validate_answers(ATTRIBUTE_VERSION,a,final=True)
        for item in ('S1','U1'):
            a=answers(True);a[item]={'status':'unable_to_judge','value':None}
            with self.assertRaises(APIError):validate_answers(NATURAL_VERSION,a)
        a=answers(True);a['S1']['value']=6
        with self.assertRaises(APIError):validate_answers(NATURAL_VERSION,a)
    def test_unanswered_cannot_be_silently_submitted(self):
        with self.assertRaises(APIError): validate_answers(ATTRIBUTE_VERSION,{},final=True)
        a=answers(True);a['S1']={'status':'unanswered','value':None}
        with self.assertRaises(APIError):validate_answers(NATURAL_VERSION,a,final=True)
    def test_scoring_extremes(self):
        a=validate_answers(NATURAL_VERSION,answers(True),final=True)
        self.assertEqual(scores(a)['sus']['value'],100);self.assertEqual(scores(a)['ueq_pragmatic']['value'],3)
        for i in range(1,11):a[f'S{i}']['value']=1 if i%2 else 5
        self.assertEqual(scores(a)['sus']['value'],0)


class HTTP(unittest.TestCase):
    def test_post_restart_read_and_idempotent_resend(self):
        with tempfile.TemporaryDirectory() as td:
            packet={'request_id':uid(),'operation':'create_run','expected_revision':0,'payload_json':encoded({'participant_id':'ENG-http','collection_kind':'engineering','execution_mode':'mock','manifest':manifest()})}
            saved=None
            for _ in range(2):
                server=Server(('127.0.0.1',0),Experiment(MockModel(),td));thread=threading.Thread(target=server.serve_forever);thread.start()
                try:
                    conn=HTTPConnection('127.0.0.1',server.server_address[1],timeout=3)
                    conn.request('POST','/study/commands',encoded(packet),{'Content-Type':'application/json'})
                    response=conn.getresponse();self.assertEqual(response.status,200);ack=json.loads(response.read())
                    if saved:self.assertEqual(ack['study_run_id'],saved['study_run_id']);self.assertTrue(ack['idempotent_replay'])
                    saved=ack
                    conn.request('GET','/study/runs/'+ack['study_run_id']);response=conn.getresponse();self.assertEqual(response.status,200);self.assertEqual(json.loads(response.read())['revision'],0)
                    conn.close()
                finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__': unittest.main()
