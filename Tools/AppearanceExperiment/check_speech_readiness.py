"""Offline configuration checks only: no sourcing, network, or credential output."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Backend'))
from speech import SpeechConfig

FIELDS = {'QWEN_API_KEY', 'QWEN_BASE_URL', 'QWEN_ASR_MODEL',
          'QWEN_TTS_MODEL', 'QWEN_TIMEOUT_SECONDS'}
MODELS = {'QWEN_ASR_MODEL': 'qwen-audio-3.0-asr-flash',
          'QWEN_TTS_MODEL': 'qwen-audio-3.0-tts-plus'}


def read_literals(path):
    """Accept literal KEY=value assignments, never execute a private shell file."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, raw = line.partition('=')
        key = key.strip()
        if key not in FIELDS:
            continue
        if not separator or '$' in raw or '`' in raw:
            raise ValueError('literal_assignments_required')
        parts = shlex.split(raw, comments=True)
        if len(parts) > 1:
            raise ValueError('literal_assignments_required')
        values[key] = parts[0] if parts else ''
    return values


def inspect(values):
    errors = []
    warnings = []
    key = values.get('QWEN_API_KEY', '')
    base = values.get('QWEN_BASE_URL', '').rstrip('/')
    for field in ('QWEN_API_KEY', 'QWEN_BASE_URL'):
        if not values.get(field, '').strip():
            errors.append('missing_' + field.lower())
    plan_key = key.startswith('sk-sp-')
    plan_endpoint = base == 'https://token-plan.cn-beijing.maas.aliyuncs.com'
    if plan_key != plan_endpoint:
        errors.append('credential_endpoint_plan_mismatch')
    if plan_key or plan_endpoint:
        warnings.append('token_plan_provider_scope_restricted_to_interactive_ai_tools')
    models = {field: values.get(field, default) for field, default in MODELS.items()}
    if models != MODELS:
        errors.append('model_profile_differs_review_required')
    try:
        SpeechConfig(base, key, models['QWEN_ASR_MODEL'], models['QWEN_TTS_MODEL'],
                     float(values.get('QWEN_TIMEOUT_SECONDS', '30')))
    except (TypeError, ValueError):
        errors.append('invalid_or_incomplete_speech_configuration')
    return {'mode': 'offline', 'configuration_ready': not errors,
            'provider_access_verified': False, 'network_calls': 0,
            'credentials_modified': False, 'errors': errors, 'warnings': warnings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, help='Private file with literal QWEN assignments')
    args = parser.parse_args(argv)
    default = ROOT / '.env'
    if not default.is_file():
        default = Path.home() / '.config/aiaa4435/appearance.env'
    path = args.env_file or Path(os.environ.get('APPEARANCE_ENV_FILE') or default)
    values = {field: os.environ[field] for field in FIELDS if field in os.environ}
    file_error = None
    try:
        values.update(read_literals(path))
    except (OSError, UnicodeError):
        file_error = 'configuration_file_unreadable'
    except ValueError:
        file_error = 'literal_assignments_required'
    report = inspect(values)
    if file_error:
        report['errors'].append(file_error)
        report['configuration_ready'] = False
    print(json.dumps(report, indent=2))
    return 0 if report['configuration_ready'] else 1


if __name__ == '__main__':
    sys.exit(main())
