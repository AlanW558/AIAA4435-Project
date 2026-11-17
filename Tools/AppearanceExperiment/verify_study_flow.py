#!/usr/bin/env python3
"""Real Unity controllers against local fixture models; no cloud or microphone calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Backend'),str(ROOT/'Backend/tests')]
from core import Experiment
from server import Server
from test_tutor_generation import GenerationFixture
from test_tutor_interpretation import tailoring
from test_tutor_session import chat
from export_study_data import export_run

class FlowModel(GenerationFixture):
    def interpret_tutor(self,context):
        self.raw=chat('Explain recall.') if 'Natural conversation' in context.get('query','') else tailoring('brief',kind='mixed',conversation_query='Explain recall.')
        return super().interpret_tutor(context)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    backend=Server(('127.0.0.1',0),Experiment(FlowModel(),out/'backend'))
    thread=threading.Thread(target=backend.serve_forever,daemon=True);thread.start()
    env=dict(os.environ,TUTOR_BACKEND_URL=f'http://127.0.0.1:{backend.server_address[1]}',IAI_STUDY_JOURNAL_DIR=str(out/'client-journal'),IAI_STUDY_CHECK_OUT=str(out))
    unity='/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity'
    try:
        run=subprocess.run([unity,'-batchmode','-nographics','-projectPath',str(ROOT),'-executeMethod','TutorStudyFlowSetup.RunChecks','-logFile',str(out/'unity.log')],env=env,timeout=600)
        report=out/'unity-flow.json'
        if report.exists():
            data=json.loads(report.read_text())
            if data.get('study_run_id'):
                result=export_run(backend.study,data['study_run_id'],out/'export',out/'client-journal')
                data['export_counts']=result['counts'];data['export_status']=result['export_status'];report.write_text(json.dumps(data,indent=2)+'\n')
            print(json.dumps(data))
        else:print('Unity did not produce a completed flow report; inspect '+str(out/'unity.log'))
        return run.returncode
    finally:backend.shutdown();backend.server_close();thread.join()

if __name__=='__main__':raise SystemExit(main())
