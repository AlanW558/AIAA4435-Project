#!/usr/bin/env python3
"""Explicit automatic speech/recovery acceptance. No microphone recording.

--execute-speech uses the configured Qwen service, bounded to 4 ASR + 4 TTS
attempts across restarts, with no automatic provider retry. Tutor reasoning is
an explicit fixture: this test validates voice transport/storage, not DeepSeek.
All WAV inputs are labeled, locally synthesized test utterances.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Backend'),str(ROOT/'Backend/tests'),str(Path(__file__).parent)]
from core import Experiment
from server import Server,Handler
from speech import SpeechConfig,SpeechService,QwenTransport,SpeechError
from check_speech_readiness import read_literals
from verify_study_flow import FlowModel
from study_store import StudyStore,uid,encoded
from export_study_data import export_run
from test_study_store import Fixture


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)

class MeteredTransport(QwenTransport):
    def __init__(self,config,out):super().__init__(config);self.out=out;self.lock=threading.Lock()
    def post(self,route,payload):
        kind='tts' if '/tts/' in route else 'asr'
        with self.lock:
            file=self.out/'provider-calls.json';ledger=json.loads(file.read_text()) if file.exists() else []
            if sum(x['kind']==kind for x in ledger)>=4:raise SpeechError('acceptance_call_limit')
            index=len(ledger);ledger.append({'kind':kind,'model':payload['model'],'status':'attempting'})
            save(file,ledger)
        try:result=super().post(route,payload)
        except SpeechError as exc:
            with self.lock:
                ledger=json.loads(file.read_text());ledger[index].update(status=exc.code,http_status=exc.status);save(file,ledger)
            raise
        with self.lock:
            ledger=json.loads(file.read_text());ledger[index].update(status='provider_returned',request_id=result.get('request_id'));save(file,ledger)
        return result


def worker(args):
    if args.fixture_speech:
        from test_speech import FakeTransport
        class LocalSpeech(SpeechService):
            def transcribe(self,audio,**kwargs):
                return {'text':'The response was easy to follow, and the adjustment matched my request.' if audio==(args.out/'comment-synthetic.wav').read_bytes() else 'Make the answer brief and explain active recall.'}
        speech=LocalSpeech(SpeechConfig('https://fixture.cn-beijing.maas.aliyuncs.com','fixture-not-a-key'),FakeTransport())
    else:
        values=read_literals(ROOT/'.env')
        config=SpeechConfig(values['QWEN_BASE_URL'],values['QWEN_API_KEY'],values['QWEN_ASR_MODEL'],values['QWEN_TTS_MODEL'],45)
        speech=SpeechService(config,MeteredTransport(config,args.out))
    parse,send=Handler.parse_body,Handler.send_json
    def parsed(self,*a,**k):
        body=parse(self,*a,**k);self.acceptance_body=body;return body
    def sent(self,status,data):
        b=getattr(self,'acceptance_body',{})
        marker='drop-submit.once' if self.path=='/study/commands' and b.get('operation')=='submit_task' else 'drop-runtime.once' if self.path.endswith('/settings') else None
        if status<300 and marker and (args.out/marker).exists():
            (args.out/marker).unlink();save(args.out/(marker+'.dropped.json'),{'status_committed':status,'request_id':b.get('request_id')})
            self.close_connection=True
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            self.connection.close();return
        return send(self,status,data)
    Handler.parse_body=parsed;Handler.send_json=sent
    model=FlowModel();server=Server(('127.0.0.1',args.port),Experiment(model,args.out/'backend'),speech=speech)
    save(args.out/'worker-ready.json',{'port':server.server_address[1],'pid':os.getpid(),'speech_live':not args.fixture_speech,'tutor_model':'fixture'})
    server.serve_forever()


def request(base,path,data=None,binary=False):
    body=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=140) as r:result=r.read()
    return result if binary else json.loads(result)

class Harness:
    def __init__(self,out,fixture=False):self.out=out;self.process=None;self.port=0;self.starts=0;self.fixture=fixture
    @property
    def base(self):return f'http://127.0.0.1:{self.port}'
    def start(self):
        ready=self.out/'worker-ready.json'
        if ready.exists():ready.unlink()
        self.starts+=1
        log=(self.out/f'worker-{self.starts}.log').open('w')
        self.process=subprocess.Popen([sys.executable,__file__,'--worker','--execute-speech','--out',str(self.out),'--port',str(self.port)]+(['--fixture-speech'] if self.fixture else []),stdout=log,stderr=log);log.close()
        until=time.monotonic()+20
        while time.monotonic()<until and not ready.exists():
            if self.process.poll() is not None:raise RuntimeError('Local speech worker did not start; inspect sanitized worker log.')
            time.sleep(.1)
        if not ready.exists():raise RuntimeError('Local worker startup timed out.')
        self.port=json.loads(ready.read_text())['port']
    def crash_restart(self):
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=10)
        ledger=self.out/'provider-calls.json';before=ledger.read_text() if ledger.exists() else ''
        self.start()
        assert (ledger.read_text() if ledger.exists() else '')==before,'Startup must not replay any provider work.'
    def stop(self):
        if self.process and self.process.poll() is None:self.process.terminate();self.process.wait(timeout=15)
    def unity(self,phase):
        env=dict(os.environ,TUTOR_BACKEND_URL=self.base,IAI_STUDY_JOURNAL_DIR=str(self.out/'client-journal'),IAI_STUDY_CHECK_OUT=str(self.out),IAI_STUDY_RECOVERY_PHASE=str(phase),IAI_STUDY_OFFLINE_FAULT="1" if self.fixture else "0")
        unity='/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity'
        stop=threading.Event()
        def disconnect():
            while not stop.wait(.1):
                flag=self.out/'disconnect.once'
                if flag.exists():
                    flag.unlink();self.process.kill();self.process.wait(timeout=10)
                    save(self.out/'disconnected.json',{'backend_stopped_before_request':True});return
        watcher=threading.Thread(target=disconnect,daemon=True);watcher.start()
        try:
            p=subprocess.run([unity,'-batchmode','-nographics','-projectPath',str(ROOT),'-executeMethod','TutorStudyFlowSetup.RunChecks','-logFile',str(self.out/f'unity-phase-{phase}.log')],env=env,timeout=360)
        finally:stop.set();watcher.join(timeout=15)
        file=self.out/f'phase-{phase}.json'
        if not file.exists():raise RuntimeError('Unity did not finish phase '+str(phase))
        data=json.loads(file.read_text());print(json.dumps({'phase':phase,**data}),flush=True)
        if p.returncode or not data['passed']:raise RuntimeError('Unity phase failed; inspect phase report.')
        return data

class HTTPFixture(Fixture):
    def __init__(self,folder,base):self.base=base;super().__init__(folder)
    def send(self,op,payload):
        ack=request(self.base,'/study/commands',self.packet(op,payload))
        if op=='create_run':self.run=ack['study_run_id']
        return ack['result']


def natural(h):
    # Separate one-task engineering fixture prepares the natural module only.
    # It is explicitly not a shortened participant protocol.
    f=HTTPFixture(h.out/'backend/study',h.base);f.finish_attributes();mid=f.module(None)
    sid=f.send('launch_runtime',{'target_id':mid})['runtime_id'];route='/tutor/sessions/'+sid
    view=request(h.base,route)
    payload={'request_id':uid(),'expected_revision':view['revision'],'condition':'S','question_id':'','audio_base64':base64.b64encode((h.out/'request-synthetic.wav').read_bytes()).decode()}
    transcript=request(h.base,route+'/transcribe',payload)['text']
    view=request(h.base,route+'/request',{'request_id':uid(),'expected_revision':view['revision'],'query':transcript})
    if view.get('question'):
        view=request(h.base,route+'/answer',{'request_id':uid(),'expected_revision':view['revision'],'question_id':view['question']['question_id'],'option_id':'c1'})
    for job in view['generation_jobs']:
        if job['status']=='queued':view=request(h.base,route+'/generate',{'request_id':uid(),'expected_revision':view['revision'],'job_id':job['job_id']})
    audio=request(h.base,route+'/audio',{'request_id':uid(),'expected_revision':view['revision'],'condition':'S','purpose':'reply','exchange_id':view['conversation'][-1]['id']},binary=True)
    (h.out/'natural-tutor-reply.wav').write_bytes(audio)
    f.send('finish_natural',{'module_instance_id':mid});f.feedback(mid,None)
    before=f.state['questionnaires'];h.crash_restart()
    assert f.state['questionnaires']==before,'Saved natural answers must survive forced backend termination.'
    f.send('submit_natural',{'module_instance_id':mid,'evaluation_revision':1});f.send('end_run',{'end_reason':'normal_completion'})
    result=export_run(f.store,f.run,h.out/'natural-export')
    assert result['counts']['natural_feedback']==1
    return {'study_run_id':f.run,'transcript':transcript,'counts':result['counts'],'export_status':result['export_status'],'fixture_preparation':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute-speech',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--port',type=int,default=0);p.add_argument('--fixture-speech',action='store_true',help='No cloud calls; includes a real connection-loss fault')
    args=p.parse_args();args.out=args.out.resolve()
    if not args.execute_speech and not args.fixture_speech:raise SystemExit('Explicit --execute-speech is required for real API calls.')
    if args.worker:return worker(args)
    args.out.mkdir(parents=True,exist_ok=False)
    for name,text in [('request','Make the answer brief and explain active recall.'),('comment','The response was easy to follow, and the adjustment matched my request.')]:
        subprocess.run(['/usr/bin/say','-v','Samantha','--file-format=WAVE','--data-format=LEI16@16000','-o',str(args.out/(name+'-synthetic.wav')),text],check=True)
    save(args.out/'synthetic-inputs.json',{'source':'macOS Samantha text-to-speech','participant_recordings':False,'microphone_used':False})
    h=Harness(args.out,args.fixture_speech);report={'passed':False,'live_qwen':not args.fixture_speech,'tutor_reasoning':'fixture','microphone_used':False,'headset_tested':False,'heard_audio_verified':False,'phases':[]}
    try:
        h.start()
        for phase in (1,2,3):
            report['phases'].append(h.unity(phase))
            if phase<3:h.crash_restart()
        store=StudyStore(args.out/'backend/study');run=report['phases'][0]['study_run_id']
        result=export_run(store,run,args.out/'interrupted-export',args.out/'client-journal')
        assert result['counts']['attribute_feedback']==8
        reconciliation=json.loads((args.out/'interrupted-export/local_reconciliation.json').read_text())
        assert reconciliation['status']=='provided_copy_reconciled'
        transcript=(args.out/'survey-transcript.txt').read_text()
        state,events=store.snapshot(run)
        assert any(q['extras']['comment']==transcript for q in state['questionnaires'].values())
        dialogue=(args.out/'interrupted-export/dialogue.jsonl').read_text()
        assert transcript not in dialogue,'Survey comments must not enter tutor conversation.'
        report['interrupted_export']={'counts':result['counts'],'status':result['export_status'],'local_reconciliation':reconciliation['status']}
        report['natural']=natural(h)
        report['passed']=True
    except Exception as exc:
        # Never serialize raw provider errors, credentials, signed URLs or HTTP bodies.
        report['failure_type']=type(exc).__name__
        print('Acceptance stopped:',type(exc).__name__,'Inspect local phase reports.',flush=True)
    finally:
        h.stop();report['worker_starts']=h.starts
        ledger=args.out/'provider-calls.json';report['provider_calls']=json.loads(ledger.read_text()) if ledger.exists() else []
        save(args.out/'acceptance.json',report)
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
