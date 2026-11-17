#!/usr/bin/env python3
"""Local synthetic study persistence verification. No model/audio calls or real participants."""
import argparse
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'Backend'))
sys.path.insert(0, str(PROJECT / 'Backend/tests'))
from test_study_store import Fixture
from export_study_data import export_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='New validation directory; never overwrites')
    args = parser.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    suite = unittest.defaultTestLoader.discover(str(PROJECT / 'Backend/tests'))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        (out/'summary.json').write_text(json.dumps({'passed':False,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}))
        return 1
    full = Fixture(out/'synthetic-backend', full=True)
    full.finish_attributes(); mid = full.natural(); full.feedback(mid, None)
    full.send('submit_natural', {'module_instance_id':mid,'evaluation_revision':1})
    full.send('end_run', {'end_reason':'normal_completion'})
    complete = export_run(full.store, full.run, out/'complete-example')
    partial = Fixture(out/'partial-backend')
    mid=partial.module();tid=partial.task(mid)
    partial.feedback(mid, tid, data={'A0':{'status':'unable_to_judge','value':None}})
    partial.send('end_run', {'end_reason':'participant_exit'})
    incomplete=export_run(partial.store,partial.run,out/'partial-example')
    summary={'passed':True,'backend_tests':result.testsRun,'complete_export_counts':complete['counts'],
             'partial_export_counts':incomplete['counts'],'collection_kind':'engineering','execution_mode':'mock',
             'real_participants':0,'provider_calls':0,'microphone_recordings':0,'headset_tested':False,
             'scope':'New study storage API, restart/idempotency, failure rollback, full and partial export; old tutor runtime and questionnaire UI are not migrated.'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'validation_directory':str(out),'summary':summary},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
