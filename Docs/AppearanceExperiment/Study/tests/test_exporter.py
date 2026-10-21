"""Engineering-only exporter tests; temporary mock/debug data never become study results.

Renderer payloads below are explicit test fixtures, not evidence from a headset.
"""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO/'Backend'))
from core import Experiment
from model import MockModel
spec=importlib.util.spec_from_file_location('export_study',REPO/'Tools/AppearanceExperiment/export_study.py')
exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
STUDY=REPO/'Docs/AppearanceExperiment/Study'

class ExporterEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=Experiment(MockModel(),self.root/'logs')
        self.view=self.app.create({'participant_id':'ENGINEERING_EXPORT_TEST','condition':'E','phase':'debug'})
        self.sid=self.view['session_id'];self.counter=0
        self.mutate('reset',state={'jacket_color':'blue','accessory':'hat','scale':1.0},history=[],soft_preferences=[],task_id='A_T1')
        self.mutate('request',query='把外衣改成橙色，帽子和大小保持不变。')
    def tearDown(self):self.temp.cleanup()
    def mutate(self,operation,**payload):
        self.counter+=1
        self.view=self.app.mutate(self.sid,operation,{'request_id':f'fixture_{self.counter}','expected_revision':self.view['state']['revision'],**payload})
        return self.view
    def event(self,name,payload):self.app.event(self.sid,{'event':name,'payload':payload})
    def render_fixture(self,name,**extra):
        state=self.app.view(self.app.get(self.sid))['state']
        self.event(name,{'revision':state['revision'],'state':{k:state[k] for k in exporter.FIELDS},'message':'ENGINEERING FIXTURE — not measured Unity/headset evidence',**extra})
    def result(self,phase='debug'):
        return exporter.export(self.root/'logs',self.root/('export_'+phase),phase,STUDY/'materials/tasks_private.json',STUDY/'materials/participant_schedule.csv')
    def test_default_formal_excludes_mock_debug(self):
        with self.assertRaisesRegex(ValueError,'No observed formal'):
            self.result('formal')
        self.assertFalse((self.root/'export_formal').exists())
    def test_missing_renderer_is_missing_not_success(self):
        self.mutate('finish')
        report,path=self.result()
        with path.open() as stream:row=next(csv.DictReader(stream))
        self.assertEqual(row['first_commit_success'],'')
        self.assertEqual(row['stable_goal_success'],'')
        self.assertEqual(row['elapsed_ms'],'')
        self.assertFalse(report['analysis_ready'])
        self.assertEqual(report['evidence_class'],'engineering_debug_not_participant_results')
    def test_three_distinct_probes_and_compatible_columns(self):
        self.render_fixture('render_ack')
        self.event('client_marker',{'kind':'completion','value':'engineering_done','elapsed_seconds':2.25,'block':1,'study_session_id':'ENGINEERING_EXPORT_TEST_ONLY'})
        for index in (1,2,3):self.render_fixture('probe',probe_index=index,duration_ms=10)
        self.mutate('finish')
        report,path=self.result()
        with path.open() as stream:
            reader=csv.DictReader(stream);row=next(reader);fields=reader.fieldnames
        with (STUDY/'materials/trial_results_EMPTY_TEMPLATE.csv').open() as stream:
            self.assertEqual(fields,next(csv.reader(stream)))
        self.assertEqual(row['first_commit_success'],'1')
        self.assertEqual(row['stable_goal_success'],'1')
        self.assertEqual(row['elapsed_ms'],'2250.0')
        self.assertEqual(row['probe_ms'],'30')
        self.assertEqual(row['timeout'],'0')
        self.assertFalse(report['analysis_ready'])
    def test_repeat_one_probe_does_not_replace_three_probes(self):
        self.render_fixture('render_ack')
        for _ in range(3):self.render_fixture('probe',probe_index=1,duration_ms=10)
        self.mutate('finish')
        _,path=self.result()
        with path.open() as stream:row=next(csv.DictReader(stream))
        self.assertEqual(row['stable_goal_success'],'')
    def test_no_first_commit_before_repair_is_failure(self):
        # Unit-level chronology test: a later repair cannot repair the first-commit metric.
        records,_=exporter.load_logs(self.root/'logs')
        trial=[e for e in records if e['trial_id']==self.view['trial_id']]
        commit_index=next(i for i,e in enumerate(trial) if e['event']=='commit')
        repair={**trial[commit_index],'event':'user_request','initial':False,'query':'engineering fixture repair'}
        trial.insert(commit_index,repair)
        trial.append({**trial[-1],'event':'trial_finished','repair_count':1})
        task=json.loads((STUDY/'materials/tasks_private.json').read_text())[0]
        row,_=exporter.assess_trial(trial,task,{})
        self.assertEqual(row['first_commit_success'],0)
    def test_overlapping_wait_intervals_not_double_counted(self):
        self.assertEqual(exporter.union_ms([(0,100),(50,150),(200,250)]),200)

if __name__=='__main__':unittest.main()
