"""Bind actual tutor execution to the new study store and retain its audit evidence."""
import json
import threading
from pathlib import Path
from copy import deepcopy
from core import APIError
from study_store import require, keys, uid, encoded, digest, now
from tutor_state import DEFAULT_SETTINGS
from tutor_study_materials import public_start
from tutor_feedback import ATTRIBUTE_VERSION
from study_runtime import comparison_dump, comparison_load, session_dump, session_load


class StudyFlow:
    def __init__(self, server):
        self.server=server;self.store=server.study;self.lock=threading.RLock()
        self.blocked=set()
        with self.store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS study_runtimes(id TEXT PRIMARY KEY,kind TEXT,run_id TEXT,target_id TEXT,snapshot TEXT,inflight TEXT,offset INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS runtime_receipts(key TEXT PRIMARY KEY,signature TEXT,response TEXT);''')
            rows=db.execute('SELECT id,kind,snapshot,inflight FROM study_runtimes').fetchall()
        for rid,kind,snapshot,inflight in rows:
            if not snapshot: self.blocked.add(rid);continue
            data=json.loads(snapshot)
            if inflight or data.get('processing'):self.blocked.add(rid);continue
            if kind=='comparisons':server.comparisons.tasks[rid]=comparison_load(server.comparisons,data)
            else:server.tutor.sessions[rid]=session_load(data['session'])
        self.store.executor=self
        for rid,_,_,_ in rows:self.checkpoint(rid,audit_only=True)

    def launch(self, db, s, p):
        keys(p,('target_id',))
        target=s['tasks'].get(p['target_id']) or s['modules'].get(p['target_id'])
        require(target is not None,'target_not_found','Choose a registered task or natural module.')
        if target.get('runtime_id'):return {'runtime_id':target['runtime_id'],'kind':target['runtime_kind']}
        natural=target.get('module_type')=='natural_selective'
        if natural:
            view=self.server.tutor.create({'participant_id':s['participant_id'],'condition':'S','settings':target['initial_state']})
            rid=view['session_id'];kind='sessions';snapshot={'kind':kind,'session':session_dump(self.server.tutor.get(rid)),'processing':False}
        else:
            # Same fixed public baseline/history as existing task materials, never private instructions.
            sequence=s['manifest'].get('execution_sequence')
            data={'request_id':uid(),'participant_id':s['participant_id'],'task_code':target['task_code'],'domain':target['domain'],'scenario':target['scenario'],'feedback_version':ATTRIBUTE_VERSION,'require_preparation':True}
            if sequence:data['sequence']=sequence
            index=next(i for i,t in enumerate(s['manifest']['tasks']) if t['task_code']==target['task_code'])
            view=self.server.comparisons.create(data,lineage=(s['study_run_id'],index+1,None) if sequence else None)
            rid=view['task_id'];kind='comparisons';snapshot=comparison_dump(self.server.comparisons.get(rid))
        target['runtime_id']=rid;target['runtime_kind']=kind
        if natural:target['session_id']=rid
        db.execute('INSERT INTO study_runtimes VALUES (?,?,?,?,?,?,0)',(rid,kind,s['study_run_id'],p['target_id'],encoded(snapshot),None))
        return {'runtime_id':rid,'kind':kind}

    def bound(self,rid):
        with self.store.connect() as db:return db.execute('SELECT kind,run_id,target_id,offset FROM study_runtimes WHERE id=?',(rid,)).fetchone()

    def guard(self,rid):
        if rid in self.blocked:raise APIError(409,'runtime_reconciliation_required','Execution was interrupted. Saved study data are retained; end this attempt without replaying model calls.')

    def checkpoint(self,rid,audit_only=False):
        with self.lock:self._checkpoint(rid,audit_only)

    def _checkpoint(self,rid,audit_only=False):
        binding=self.bound(rid)
        if not binding:return
        if not audit_only:self.guard(rid)
        kind,run_id,target_id,_=binding
        if audit_only:
            with self.store.connect() as db:snapshot=json.loads(db.execute('SELECT snapshot FROM study_runtimes WHERE id=?',(rid,)).fetchone()[0])
            path=(self.server.comparisons.log_dir if kind=='comparisons' else self.server.tutor.log_dir)/(rid+'.jsonl')
        elif kind=='comparisons':
            rt=self.server.comparisons.get(rid); snapshot=comparison_dump(rt);path=self.server.comparisons.log_dir/(rid+'.jsonl')
        else:
            obj=self.server.tutor.get(rid)
            with obj.lock:snapshot={'kind':kind,'session':session_dump(obj),'processing':False}
            path=self.server.tutor.log_dir/(rid+'.jsonl')
        # Import exact JSONL events once. Audit additions during this read are imported on the next checkpoint.
        raw=path.read_bytes() if path.exists() else b''
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            offset=db.execute('SELECT offset FROM study_runtimes WHERE id=?',(rid,)).fetchone()[0]
            require(len(raw)>=offset,'audit_truncated','Runtime audit was truncated; cannot certify saved evidence.',503)
            tail=raw[offset:];end=tail.rfind(b'\n')+1
            state=self.store._load(db,run_id)
            for line in tail[:end].splitlines():
                record=json.loads(line)
                event={'event_id':uid(),'timestamp_utc':now(),'event':'runtime_audit','study_run_id':run_id,
                       'participant_id':state['participant_id'],'collection_kind':state['collection_kind'],
                       'runtime_id':rid,'target_id':target_id,'runtime_kind':kind,'record':record}
                db.execute('INSERT INTO events(run_id,payload) VALUES (?,?)',(run_id,encoded(event)))
            if audit_only:db.execute('UPDATE study_runtimes SET offset=? WHERE id=?',(offset+end,rid))
            else:db.execute('UPDATE study_runtimes SET snapshot=?,offset=? WHERE id=?',(encoded(snapshot),offset+end,rid))
            db.execute('COMMIT')

    def before(self,rid,operation,data):
        if not self.bound(rid):return None
        key=rid+':'+data.get('request_id','');signature=digest(encoded({'op':operation,'data':data}))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT signature,response FROM runtime_receipts WHERE key=?',(key,)).fetchone()
            if row:
                require(row[0]==signature,'request_id_conflict','Runtime request ID was reused with different content.',409)
                db.execute('COMMIT')
                result=json.loads(row[1]);self.guard(rid)
                kind=self.bound(rid)[0]
                live=self.server.comparisons.view(self.server.comparisons.get(rid)) if kind=='comparisons' else self.server.tutor.view(self.server.tutor.get(rid))
                result['body']={**live,**({k:v for k,v in result['body'].items() if k in ('error','message','decision')} if result['status']>=400 else {}),'idempotent_replay':True}
                return result
            self.guard(rid)
            binding=self.bound(rid); state=self.store.read(binding[1]);target=state['tasks'].get(binding[2]) or state['modules'].get(binding[2])
            require(state['lifecycle']=='active' and not target.get('frozen') and not target.get('submission_id'),'study_interaction_locked','Study is paused, ended, or already submitted.',409)
            require(operation.split(':')[0] not in ('submit','next','feedback','preference','preference_pause','preference_resume','preference_exit'), 'use_study_panel','Use the durable study panel to submit evaluations.',409)
            inflight=db.execute('SELECT inflight FROM study_runtimes WHERE id=?',(rid,)).fetchone()[0]
            require(inflight is None,'runtime_busy','Another runtime command is unresolved; restore or inspect it.',409)
            db.execute('UPDATE study_runtimes SET inflight=? WHERE id=?',(encoded({'operation':operation,'data':data,'received_at':now()}),rid))
            db.execute('COMMIT')
        return None

    def after(self,rid,operation,data,response):
        if not self.bound(rid):return
        self.checkpoint(rid)
        key=rid+':'+data.get('request_id','');signature=digest(encoded({'op':operation,'data':data}))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO runtime_receipts VALUES (?,?,?)',(key,signature,encoded(response)))
            db.execute('UPDATE study_runtimes SET inflight=NULL WHERE id=?',(rid,));db.execute('COMMIT')

    def evaluate(self,s,p,natural=False):
        target=s['modules'].get(p.get('module_instance_id')) if natural else s['tasks'].get(p.get('task_id'))
        require(target and target.get('runtime_id'),'runtime_missing','Launch the linked tutor before evaluating.')
        rid=target['runtime_id'];self.guard(rid)
        with self.store.connect() as db:pending=db.execute('SELECT inflight FROM study_runtimes WHERE id=?',(rid,)).fetchone()[0]
        require(pending is None,'runtime_busy','Wait for the current tutor operation before evaluating.',409)
        if natural:
            view=self.server.tutor.view(self.server.tutor.get(rid))
            require(not view.get('question') and all(j['status']=='completed' for j in view.get('generation_jobs',[])), 'pending_requests','Resolve/cancel clarification and finish pending replies before entering the questionnaire.',409)
            return {'module_instance_id':p['module_instance_id'],'pending_requests':0,'end_reason':'participant_finished','final_state':view}
        view=self.server.comparisons.view(self.server.comparisons.get(rid))
        require(view['results_visible'] and all(b['status'] in ('ready','stopped') for b in view['branches'].values()),'results_pending','Finish clarification before rating the strategies.',409)
        return {'task_id':p['task_id'],'first_reveal_id':view['first_reveal']['reveal_id'],
                'branches':{c:{'branch_revision':b['branch_revision'],'state_revision':b['result']['state']['revision'], 'status':b['status'],'result':b['result']} for c,b in view['branches'].items()}}

    def transcribe(self,run_id,data):
        import base64
        import hashlib
        from speech import validate_wav, MAX_AUDIO, SpeechError
        service=self.server.transcription
        require(service.speech is not None,'speech_unconfigured','Speech recognition is not configured.',503)
        keys(data,('request_id','expected_revision','condition','question_id','audio_base64'))
        def context():
            state=self.store.read(run_id)
            require(state['lifecycle']=='active' and type(data['expected_revision']) is int and state['revision']==data['expected_revision'],'stale_speech_context','Questionnaire context changed.',409)
            q=state['questionnaires'].get(data['question_id'])
            valid=(q is not None and q['record_stage']=='draft' and q['condition']==data['condition'])
            if data['condition']=='preference':
                scope=data['question_id']; planned=[t for t in state['manifest']['tasks'] if scope=='comparison_overall' or t['domain']==scope]
                done=self.store._submitted_tasks(state,None if scope=='comparison_overall' else scope)
                valid=bool(planned) and len(planned)==len(done) and scope not in state['preferences']
            require(valid,'stale_speech_context','Comment is not bound to an editable questionnaire or preference.',409)
        context()
        try:
            require(isinstance(data['audio_base64'],str) and len(data['audio_base64'])<=((MAX_AUDIO+2)//3)*4,'invalid_audio','Audio is too large.')
            audio=base64.b64decode(data['audio_base64'],validate=True);validate_wav(audio,participant=True)
        except (ValueError,SpeechError):raise APIError(400,'invalid_audio','Use a valid short PCM WAV.') from None
        key=('study-survey',run_id,data['request_id']);fingerprint=(hashlib.sha256(audio).hexdigest(),data['expected_revision'],data['condition'],data['question_id'])
        with service.lock:
            if key in service.entries:
                old,result=service.entries[key];require(old==fingerprint,'speech_request_conflict','Speech ID already used.',409)
                if isinstance(result,APIError):raise result
                context();return result
            require(len(service.entries)<service.limit,'speech_capacity','Speech request capacity reached.',503)
            service.entries[key]=(fingerprint,APIError(502,'speech_failed','Speech recognition did not finish. Record again.'))
            try:result={'text':service.speech.transcribe(audio)['text'],'request_id':data['request_id']}
            except SpeechError:raise APIError(502,'speech_failed','Speech recognition failed; no audio was saved.') from None
            service.entries[key]=(fingerprint,result);context();return result

    def recover_receipt(self,run_id,packet):
        keys(packet,('study_run_id','runtime_id','operation','body'))
        require(packet['study_run_id']==run_id,'runtime_receipt_scope','Receipt belongs to a different study run.',409)
        binding=self.bound(packet['runtime_id'])
        require(binding and binding[1]==run_id,'runtime_receipt_scope','Execution is not bound to this study run.',409)
        body=packet['body']
        require(isinstance(body,dict) and isinstance(body.get('request_id'),str),'invalid_request_id','Original runtime request ID required.')
        with self.store.connect() as db:
            row=db.execute('SELECT signature,response FROM runtime_receipts WHERE key=?',(packet['runtime_id']+':'+body['request_id'],)).fetchone()
        require(row is not None,'runtime_receipt_unknown','No committed operation receipt exists. Keep the original input; do not automatically replay it.',409)
        require(row[0]==digest(encoded({'op':packet['operation'],'data':body})),'request_id_conflict','Original runtime request content does not match.',409)
        return {'recorded':True,'study_run_id':run_id,'runtime_id':packet['runtime_id'],'request_id':body['request_id'],'response':json.loads(row[1]),'replay_model_calls':False}

    def assert_current(self,s,target):
        if not target or not target.get('runtime_id'):return
        rid=target['runtime_id'];self.guard(rid)
        if target.get('module_type')=='natural_selective':return
        live=self.evaluate(s,{'task_id':target['task_id']})
        require(target.get('evaluation')==live,'stale_evaluation','Results changed. Refresh the questionnaire and reconfirm the affected evaluation.',409)
