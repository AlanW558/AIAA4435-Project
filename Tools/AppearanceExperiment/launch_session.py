#!/usr/bin/env python3
"""Launch the participant UI from researcher-only questionnaire metadata.

No answers, credentials or hidden targets are sent to the model by this script.
Use --prepare-only to verify the join without starting Unity or a backend.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SURVEY = ROOT / 'Docs/AppearanceExperiment/Study/survey'
sys.path.insert(0, str(SURVEY))
from session_identity import validate_config


def prepare(config, condition=None, task_id=None):
    identity = validate_config(config)
    phase = identity['phase']
    if condition is not None and condition not in ('E', 'A', 'N', 'S'):
        raise ValueError('Unknown condition.')
    if phase == 'formal' and (condition is not None or task_id is not None):
        raise ValueError('Formal condition and tasks come only from the frozen schedule.')
    if task_id is not None:
        tasks = json.loads((ROOT/'Assets/StreamingAssets/AppearanceStudy/tasks.json').read_text())['tasks']
        if task_id not in {task['task_id'] for task in tasks}:
            raise ValueError('Unknown task ID.')
    if phase == 'formal':
        with (ROOT/'Docs/AppearanceExperiment/Study/materials/trial_schedule.csv').open(newline='') as f:
            rows = [r for r in csv.DictReader(f) if r['participant_slot'] == identity['participant_id']]
        if len(rows) != 16:
            raise ValueError('No complete frozen schedule for this participant slot.')
    env = {
        'APPEARANCE_PARTICIPANT_ID': identity['participant_id'],
        'APPEARANCE_PHASE': phase,
        'APPEARANCE_STUDY_SESSION_ID': identity['study_session_id'],
        'APPEARANCE_CONDITION': condition or 'S',
        'APPEARANCE_ASSIGNED': '1' if phase == 'formal' else '0',
        'APPEARANCE_TASK_ID': task_id or '',
    }
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file', type=Path, required=True)
    parser.add_argument('--condition', choices=('E','A','N','S'))
    parser.add_argument('--task', help='Optional authored task for debug/pilot only; otherwise free interaction.')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    try:
        config = json.loads(args.session_file.read_text(encoding='utf-8'))
        overrides = prepare(config, args.condition, args.task)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print('关联配置已核对。参与者界面不显示编号、类型、策略、题目卡片或轮次。', flush=True)
    if overrides['APPEARANCE_PHASE'] == 'formal':
        print('研究者按分配表另行提供任务卡。每次完成修改后按 F8 继续；每四项暂停填写分轮问卷。', flush=True)
    if args.prepare_only:
        print(json.dumps(overrides, ensure_ascii=False, indent=2))
        return
    # Explicit metadata overrides stale environment values from a prior participant.
    env = dict(os.environ, **overrides)
    os.execvpe('bash', ['bash', str(ROOT/'Tools/AppearanceExperiment/run_desktop.sh')], env)


if __name__ == '__main__':
    main()
