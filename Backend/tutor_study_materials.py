"""Versioned local study materials. Only public_start enters model context.

Study preview remains debug-only; private cards and audio targets are not prompts.
Restart the backend after changing the packaged catalog.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from core import APIError

PATH = Path(__file__).resolve().parents[1] / 'Assets/Project/Resources/Tutor/StudyTaskSequence.json'
_BYTES = PATH.read_bytes()
CATALOG = json.loads(_BYTES)
DIGEST = hashlib.sha256(_BYTES).hexdigest()
VERSION = CATALOG['materials_version']
TASKS = {t['task_code']: (m['direction'], t) for m in CATALOG['modules'] for t in m['tasks']}


def is_preview(sequence):
    return bool(sequence and sequence.get('purpose') == 'study_preview')


def validate_plan(value):
    if (set(value) != {'version', 'purpose', 'materials_version', 'catalog_sha256', 'modules'} or
            value['version'] != 'attribute-sequence-v2' or value['materials_version'] != VERSION or value['catalog_sha256'] != DIGEST):
        raise APIError(400, 'materials_mismatch', 'Unity and backend must use the same study materials.')
    expected = {m['direction']: [{'task_code': t['task_code'], 'scenario': t['scenario']} for t in m['tasks']] for m in CATALOG['modules']}
    modules = value['modules']
    if (not isinstance(modules, list) or len(modules) != 4 or
            any(not isinstance(m, dict) or set(m) != {'domain', 'tasks'} or not isinstance(m['domain'], str) or
                m['domain'] not in expected or m['tasks'] != expected[m['domain']] for m in modules) or
            len({m['domain'] for m in modules}) != 4):
        raise APIError(400, 'invalid_study_sequence', 'Use all 32 registered tasks, with four unique attribute modules.')
    return deepcopy(value)


def public_start(sequence, code):
    return deepcopy(TASKS[code][1]['public_start']) if is_preview(sequence) else None


def audio_material(sequence, code, index):
    materials = TASKS[code][1]['materials'] if is_preview(sequence) else []
    if type(index) is not int or not 1 <= index <= len(materials):
        raise APIError(400, 'invalid_material', 'Choose a registered listening sample for this task.')
    return deepcopy(materials[index - 1])
