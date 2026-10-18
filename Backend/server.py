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

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,experiment):
        self.experiment=experiment
        super().__init__(address,Handler)

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
    def parse_body(self):
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            raise APIError(415,"content_type","Use Content-Type: application/json.")
        try: length=int(self.headers.get("Content-Length","0"))
        except ValueError: raise APIError(400,"invalid_length","Invalid Content-Length.")
        if length<1 or length>65536: raise APIError(413,"body_size","JSON body must be between 1 and 65536 bytes.")
        try:
            value=json.loads(self.rfile.read(length),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        except (ValueError,UnicodeDecodeError): raise APIError(400,"invalid_json","Body must be valid finite JSON.")
        if not isinstance(value,dict): raise APIError(400,"invalid_json","Body must be a JSON object.")
        return value
    def run_request(self,method):
        try:
            path=urlsplit(self.path).path.strip("/").split("/")
            app=self.server.experiment
            if method=="GET" and path==["health"]:
                return self.send_json(200,{"ok":True,"mode":app.model.mode,"model":app.model.model,"policy_version":"appearance-backend-v0.1","durability":"JSONL audit logs; active sessions are memory-only"})
            if method=="GET" and len(path)==2 and path[0]=="sessions":
                s=app.get(path[1])
                with s.lock: return self.send_json(200,app.view(s))
            if method=="POST":
                data=self.parse_body()
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
    args=parser.parse_args()
    try: model=MockModel() if args.mode=="mock" else DeepSeekModel(args.model,args.timeout)
    except ValueError as exc: parser.error(str(exc))
    app=Experiment(model,args.log_dir)
    server=Server((args.host,args.port),app)
    print(json.dumps({"status":"listening","host":args.host,"port":server.server_address[1],"mode":model.mode,"model":model.model,"log_dir":str(app.log_dir.resolve())},ensure_ascii=False),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=="__main__": main()
