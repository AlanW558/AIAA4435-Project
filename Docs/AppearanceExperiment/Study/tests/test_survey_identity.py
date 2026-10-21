"""Ephemeral engineering fixtures only; no participant responses are retained."""
import importlib.util
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[2]
sys.path.insert(0, str(STUDY/'survey'))
from import_responses import import_records, validate_record, unpack_response
from session_identity import validate_config
loader = importlib.util.spec_from_file_location('researcher_launcher', ROOT/'Tools/AppearanceExperiment/launch_session.py')
launcher = importlib.util.module_from_spec(loader)
loader.loader.exec_module(launcher)
SPEC = json.loads((STUDY/'survey/questionnaires.json').read_text())


def fixture(phase='debug', pid='DEBUG_TEST', fid='pre'):
    form = next(f for f in SPEC['forms'] if f['id'] == fid)
    answers = {q['id']: None for q in form['questions']}
    statuses = {q['id']: 'skipped' for q in form['questions']}
    if fid == 'pre':
        answers['consent'] = 'agree'; statuses['consent'] = 'answered'
        statuses['prior_survey_code'] = 'not_shown'
    return dict(schema_version=SPEC['schema_version'], form_id=fid,
                participant_id=pid, session_id=phase+'_'+pid+'_ENGINEERING_FIXTURE', phase=phase,
                block=1 if fid == 'block' else None, recorded_at_utc='2026-10-18T00:00:00Z',
                page_elapsed_ms=0, answers=answers, answer_status=statuses)


class SurveyIdentityTests(unittest.TestCase):
    def test_unified_bundle_preserves_one_person_four_rounds_and_skipped_exit(self):
        records=[fixture(fid='pre'),*[fixture(fid='block') for _ in range(4)],fixture(fid='exit')]
        for index,record in enumerate(records):
            record['content_revision']='appearance-survey-v0.1-zh-CN.4-unified'
            if record['form_id']=='block':record['block']=index
        bundle=dict(schema_version='appearance-survey-bundle-v1',content_revision=records[0]['content_revision'],
                    participant_id=records[0]['participant_id'],phase='debug',session_id=records[0]['session_id'],records=records)
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'fixtures'; source.mkdir()
            (source/'bundle.json').write_text(json.dumps(bundle))
            report=import_records(source,STUDY/'materials/participant_schedule.csv',base/'out','debug')
            self.assertEqual((report['response_files'],report['response_records'],report['participant_count'],report['block_rows']),(1,6,1,4))
            self.assertEqual(report['participants']['DEBUG_TEST']['missing_blocks'],[])
            self.assertEqual(sum(report['missing_ratings_by_reason'].values()),16)
            (source/'duplicate_page.json').write_text(json.dumps(records[1]))
            with self.assertRaisesRegex(ValueError,'Duplicate response'):
                import_records(source,STUDY/'materials/participant_schedule.csv',base/'duplicate-out','debug')
        for change in ('identity','page','revision','hidden'):
            broken=copy.deepcopy(bundle)
            if change=='identity':broken['records'][2]['session_id']='OTHER_SESSION'
            if change=='page':broken['records'][2]['block']=1
            if change=='revision':broken['records'][2]['content_revision']='other'
            if change=='hidden':broken['records'][0]['answers']['prior_survey_code']='SHOULD_BE_CLEARED'
            with self.subTest(change=change), self.assertRaises(ValueError):unpack_response(broken,SPEC)

    def test_phase_id_mismatch_rejected(self):
        with self.assertRaises(ValueError): validate_record(fixture('formal'), SPEC)
        with self.assertRaises(ValueError): validate_record(fixture('debug', 'P001'), SPEC)

    def test_default_import_accepts_one_formal_and_excludes_debug_pilot(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'fixtures'; source.mkdir()
            for phase,pid in [('formal','P002'),('pilot','PILOT01'),('debug','DEBUG_TEST')]:
                for fid in ('pre','block'):
                    (source/f'{phase}_{fid}.json').write_text(json.dumps(fixture(phase,pid,fid)))
            (source/'metadata.json').write_text(json.dumps(dict(schema_version='appearance-session-v1',participant_id='P002',phase='formal',study_session_id='formal_P002_ENGINEERING_FIXTURE')))
            report=import_records(source,STUDY/'materials/participant_schedule.csv',base/'out')
            self.assertEqual(report['participant_count'],1)
            self.assertEqual(report['block_rows'],1)
            self.assertEqual(report['excluded_response_files_by_phase'],{'debug':2,'pilot':2})
            self.assertEqual(report['session_config_files_ignored'],1)
            self.assertEqual(report['participants']['P002']['missing_blocks'],[2,3,4])
            debug=import_records(source,STUDY/'materials/participant_schedule.csv',base/'debug-out','debug')
            self.assertEqual(set(debug['participants']),{'DEBUG_TEST'})

    def test_duplicate_session_or_participant_does_not_merge_people(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'fixtures'; source.mkdir()
            a=fixture('formal','P001'); b=fixture('formal','P002','block'); b['session_id']=a['session_id']
            (source/'a.json').write_text(json.dumps(a)); (source/'b.json').write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,'multiple participants'):
                import_records(source,STUDY/'materials/participant_schedule.csv',base/'out')

    def test_launcher_preserves_exact_questionnaire_identity_and_frozen_schedule(self):
        config=dict(schema_version='appearance-session-v1',participant_id='P003',phase='formal',study_session_id='formal_P003_TEST_ONLY')
        env=launcher.prepare(config)
        self.assertEqual(env['APPEARANCE_STUDY_SESSION_ID'], config['study_session_id'])
        self.assertEqual(env['APPEARANCE_ASSIGNED'],'1')
        with self.assertRaises(ValueError): launcher.prepare(config,condition='S')
        with self.assertRaises(ValueError): validate_config(fixture())


if __name__ == '__main__': unittest.main()
