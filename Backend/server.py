#!/usr/bin/env python3
"""Run with python3 Backend/server.py --mode live --host 127.0.0.1 --port 8765."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from core import APIError, Experiment
from model import DeepSeekModel, MockModel
from tutor_session import TutorSessions
from tutor_comparison_service import TutorComparisons
from tutor_transcription import TutorTranscription
from tutor_audio import TutorAudio
from tutor_playback import TutorPlaybackAudit
from speech import SpeechConfig, SpeechService
from study_store import StudyStore
from study_flow import StudyFlow
from tutor_state import DEFAULT_SETTINGS

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,experiment,tutor=None,speech=None):
        self.experiment=experiment
        self.study=StudyStore(Path(experiment.log_dir) / "study")
        self.tutor=tutor if tutor is not None else TutorSessions(experiment.model,experiment.log_dir)
        self.comparisons=TutorComparisons(self.tutor.model, experiment.log_dir)
        self.transcription=TutorTranscription(self.tutor,self.comparisons,speech)
        self.audio=TutorAudio(self.tutor,self.comparisons,speech)
        self.playback=TutorPlaybackAudit(self.tutor,self.comparisons)
        self.tutor.audio_available=self.comparisons.audio_available=self.audio.available
        self.study_flow=StudyFlow(self)
        super().__init__(address,Handler)

    def server_close(self):
        self.comparisons.shutdown(wait=False)
        super().server_close()

class Handler(BaseHTTPRequestHandler):
    server_version="AppearanceExperiment/0.1"
    def log_message(self,fmt,*args):
        # Do not print request bodies, URLs with query data or credentials.
        pass
    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError): pass
    def parse_body(self,limit=65536):
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            raise APIError(415,"content_type","Use Content-Type: application/json.")
        try: length=int(self.headers.get("Content-Length","0"))
        except ValueError: raise APIError(400,"invalid_length","Invalid Content-Length.")
        if length<1 or length>limit: raise APIError(413,"body_size","JSON body exceeds the endpoint size limit.")
        try:
            value=json.loads(self.rfile.read(length),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        except (ValueError,UnicodeDecodeError): raise APIError(400,"invalid_json","Body must be valid finite JSON.")
        if not isinstance(value,dict): raise APIError(400,"invalid_json","Body must be a JSON object.")
        return value
    def send_audio(self, audio):
        self.send_response(200)
        self.send_header('Content-Type','audio/wav')
        self.send_header('Content-Length',str(len(audio)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        try: self.wfile.write(audio)
        except (BrokenPipeError,ConnectionResetError): pass
    def mutate_runtime(self,kind,identifier,operation,data,condition=None):
        if operation=='presentation':
            result=self.server.comparisons.mutate(identifier,operation,data,condition=condition)
            self.server.study_flow.checkpoint(identifier)
            return self.send_json(202,result)
        qualified=operation+(':'+condition if condition else '')
        cached=self.server.study_flow.before(identifier,qualified,data)
        if cached is not None:return self.send_json(cached['status'],cached['body'])
        try:
            value=(self.server.comparisons.mutate(identifier,operation,data,condition=condition) if kind=='comparisons'
                   else self.server.tutor.mutate(identifier,operation,data))
            reply={'status':202 if kind=='comparisons' else 200,'body':value}
        except APIError as exc:reply={'status':exc.status,'body':exc.body()}
        self.server.study_flow.after(identifier,qualified,data,reply)
        return self.send_json(reply['status'],reply['body'])
    def run_request(self,method):
        try:
            path=urlsplit(self.path).path.strip("/").split("/")
            app=self.server.experiment
            if method=="GET" and len(path)==4 and path[:2]==["study","runs"] and path[3]=="snapshot":
                return self.send_json(200,{"state":self.server.study.client_snapshot(path[2]),"events_included":False,"submitted_evaluations_omitted":True,"replay_model_calls":False})
            if method=="GET" and len(path)==4 and path[:2]==["study","runs"] and path[3]=="recovery":
                state,events=self.server.study.snapshot(path[2])
                return self.send_json(200,{"state":state,"events":events,"replay_model_calls":False})
            if method=="GET" and len(path)==3 and path[:2]==["study","runs"]:
                return self.send_json(200,self.server.study.read(path[2]))
            if method=="GET" and len(path)==3 and path[:2]==["study","receipts"]:
                return self.send_json(200,self.server.study.receipt(path[2]))
            if method=="GET" and path==["study","config"]:
                return self.send_json(200,{"defaults":DEFAULT_SETTINGS,"mode":app.model.mode,"model":app.model.model,"backend_build_id":"study-flow-v1"})
            if method=="GET" and path==["speech","status"]:
                return self.send_json(200,{"configured":callable(getattr(self.server.transcription.speech,'transcribe',None)),"audio_available":self.server.audio.available})
            if method=="GET" and path==["health"]:
                return self.send_json(200,{"ok":True,"mode":app.model.mode,"model":app.model.model,"policy_version":"appearance-backend-v0.1","durability":"Study-linked execution: durable checkpoints and JSONL audit imported into SQLite WAL/FULL, with questionnaire receipts; uncertain operations block replay. Engineering/practice only. Standalone legacy execution remains memory-only."})
            if method=="GET" and len(path)==2 and path[0]=="sessions":
                s=app.get(path[1])
                with s.lock: return self.send_json(200,app.view(s))
            if method=="GET" and len(path)==3 and path[:2]==["tutor","sessions"]:
                self.server.study_flow.checkpoint(path[2])
                return self.send_json(200,self.server.tutor.view(self.server.tutor.get(path[2])))
            if method=="GET" and len(path)==3 and path[:2]==["tutor","comparisons"]:
                self.server.study_flow.checkpoint(path[2])
                return self.send_json(200,self.server.comparisons.view(self.server.comparisons.get(path[2])))
            if method=="POST":
                is_speech = len(path)==4 and path[0]=="tutor" and path[1] in ("sessions","comparisons") and path[3] in ("transcribe", "survey-transcribe", "preference-transcribe")
                is_study_speech=len(path)==4 and path[:2]==["study","runs"] and path[3]=="transcribe"
                data=self.parse_body(10_700_000 if is_speech or is_study_speech else 300000 if path==["study","commands"] else 65536)
                if path==["study","commands"]:
                    if data.get('operation') in ('capture_evaluation','finish_task','finish_natural'):
                        state=self.server.study.read(data.get('study_run_id'))
                        payload=json.loads(data['payload_json']); target=state['tasks'].get(payload.get('task_id')) or state['modules'].get(payload.get('module_instance_id'))
                        if target and target.get('runtime_id') and not target.get('frozen') and not target.get('submission_id'):
                            self.server.study_flow.checkpoint(target['runtime_id'])
                    return self.send_json(200,self.server.study.command(data))
                if len(path)==4 and path[:2]==["study","runs"] and path[3]=="runtime-receipt":
                    return self.send_json(200,self.server.study_flow.recover_receipt(path[2],data))
                if is_study_speech:
                    return self.send_json(200,self.server.study_flow.transcribe(path[2],data))
                if is_speech:
                    if path[3] in ("survey-transcribe", "preference-transcribe") and path[1] != "comparisons":
                        raise APIError(400, "invalid_survey_context", "Use a comparison questionnaire context.")
                    kind = "preference" if path[3] == "preference-transcribe" else "survey" if path[3] == "survey-transcribe" else path[1]
                    return self.send_json(200,self.server.transcription.transcribe(kind,path[2],data))
                if len(path)==4 and path[0]=='tutor' and path[1] in ('sessions','comparisons') and path[3]=='playback':
                    receipt=self.server.playback.record(path[1],path[2],data)
                    self.server.study_flow.checkpoint(path[2],audit_only=True)
                    return self.send_json(200,receipt)
                if len(path)==4 and path[0]=='tutor' and path[1] in ('sessions','comparisons') and path[3]=='audio':
                    return self.send_audio(self.server.audio.synthesize(path[1],path[2],data))
                if path==["tutor","comparisons"]:
                    return self.send_json(200,self.server.comparisons.create(data))
                if len(path)==4 and path[:2]==["tutor","comparisons"]:
                    return self.mutate_runtime("comparisons",path[2],path[3],data)
                if len(path)==6 and path[:2]==["tutor","comparisons"] and path[3]=="branches":
                    return self.mutate_runtime("comparisons",path[2],path[5],data,condition=path[4])
                if path==["tutor","sessions"]: return self.send_json(200,self.server.tutor.create(data))
                if len(path)==4 and path[:2]==["tutor","sessions"]:
                    return self.mutate_runtime("sessions",path[2],path[3],data)
                if path==["sessions"]: return self.send_json(200,app.create(data))
                if len(path)==3 and path[0]=="sessions":
                    result=app.event(path[1],data) if path[2]=="events" else app.mutate(path[1],path[2],data)
                    return self.send_json(200,result)
            raise APIError(404,"endpoint_not_found","Unknown endpoint.")
        except APIError as exc: self.send_json(exc.status,exc.body())
        except Exception:
            # A private server-side traceback may contain user data; emit only a generic diagnostic.
            print("Unhandled backend error; inspect local JSONL timeline and reproduce in debug mode.",file=sys.stderr)
            self.send_json(500,{"error":"internal_error","decision":"ERROR","message":"Backend error. Refresh session state before retrying."})
    def do_GET(self): self.run_request("GET")
    def do_POST(self): self.run_request("POST")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--log-dir",default=str(Path(__file__).resolve().parent/"logs"))
    parser.add_argument("--mode",choices=("live","mock"),default="live")
    parser.add_argument("--model",default=os.environ.get("DEEPSEEK_MODEL",""))
    parser.add_argument("--timeout",type=float,default=20)
    parser.add_argument("--speech-mode",choices=("disabled","qwen"),default="disabled")
    args=parser.parse_args()
    try: model=MockModel() if args.mode=="mock" else DeepSeekModel(args.model,args.timeout)
    except ValueError as exc: parser.error(str(exc))
    app=Experiment(model,args.log_dir)
    try: speech=SpeechService(SpeechConfig.from_env()) if args.speech_mode=="qwen" else None
    except ValueError as exc: parser.error(str(exc))
    server=Server((args.host,args.port),app,speech=speech)
    print(json.dumps({"status":"listening","host":args.host,"port":server.server_address[1],"mode":model.mode,"model":model.model,"log_dir":str(app.log_dir.resolve())},ensure_ascii=False),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=="__main__": main()
