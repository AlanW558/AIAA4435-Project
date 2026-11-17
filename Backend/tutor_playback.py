"""Durable, idempotent client playback reports bound to an audited audio_ready.

Reports are evidence of client behavior, never proof of hearing/attention. A late
report may append to a closed or previous-process task; it grants no audio access.
"""
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import math
import os
import threading
import time

from core import APIError, IDENTIFIER

FIELDS = {'event_id', 'audio_request_id', 'event', 'reason', 'position_seconds', 'elapsed_seconds', 'client_time_utc'}
REASONS = {
    'started': {'play_requested'},
    'completed': {'natural_end'},
    'stopped': {'user_stop', 'new_playback', 'context_changed', 'page_changed', 'recording_started',
                'component_disabled', 'application_paused', 'task_paused', 'task_closed', 'strategy_changed', 'settings_changed'},
    'failed': {'decode_error', 'playback_error'},
}
BINDING_FIELDS = ('audio_request_id', 'condition', 'purpose', 'exchange_id', 'expected_revision', 'branch_revision',
                  'state_revision', 'reveal_id', 'text_sha256', 'speech_settings', 'audio_duration_seconds', 'settings_scope')
IDENTITY_FIELDS = ('run_id', 'participant_id', 'phase', 'mode', 'task_id', 'task_code', 'domain', 'scenario',
                   'series_id', 'sequence_index', 'session_id')


class TutorPlaybackAudit:
    def __init__(self, tutor, comparisons):
        self.tutor, self.comparisons = tutor, comparisons
        self.lock = threading.RLock()

    def record(self, kind, identifier, data):
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier) or set(data) != FIELDS:
            raise APIError(400, 'invalid_playback_report', 'Invalid playback report fields.')
        for field in ('event_id', 'audio_request_id'):
            if not isinstance(data[field], str) or not IDENTIFIER.fullmatch(data[field]):
                raise APIError(400, 'invalid_playback_report', 'Invalid playback identifier.')
        if not isinstance(data['event'], str) or data['event'] not in REASONS or not isinstance(data['reason'], str) or data['reason'] not in REASONS[data['event']]:
            raise APIError(400, 'invalid_playback_report', 'Invalid playback event or reason.')
        for field in ('position_seconds', 'elapsed_seconds'):
            value = data[field]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 86400:
                raise APIError(400, 'invalid_playback_report', 'Playback timing must be finite and non-negative.')
        try:
            stamp = data['client_time_utc']
            if not isinstance(stamp, str) or len(stamp) > 40: raise ValueError()
            if datetime.fromisoformat(stamp.replace('Z', '+00:00')).utcoffset() is None: raise ValueError()
        except (ValueError, TypeError):
            raise APIError(400, 'invalid_playback_report', 'Use a timezone-qualified client timestamp.')
        app = self.comparisons if kind == 'comparisons' else self.tutor
        try: target = app.get(identifier)
        except APIError: target = None
        # Share the active writer lock; after a server restart the immutable audio
        # binding and accepted event IDs are recovered directly from durable audit.
        guard = (target.audit_lock if kind == 'comparisons' else target.lock) if target else nullcontext()
        path = app.log_dir / (identifier + '.jsonl')
        with self.lock, guard:
            try:
                records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
            except FileNotFoundError:
                raise APIError(404, 'audio_audit_not_found', 'Original audio audit is unavailable.')
            except (ValueError, OSError):
                raise APIError(503, 'playback_audit_unavailable', 'Playback audit could not be read safely.')
            previous = [r for r in records if r.get('event') == 'playback_report']
            same = next((r for r in previous if r.get('report', {}).get('event_id') == data['event_id']), None)
            if same:
                if same['report'] != data:
                    raise APIError(409, 'playback_event_conflict', 'Event ID was already used for different content.')
                return {'recorded': True, 'event_id': data['event_id'], 'idempotent_replay': True}
            ready = [r for r in records if r.get('event') == 'audio_ready' and r.get('audio_request_id') == data['audio_request_id']]
            if not ready:
                raise APIError(409, 'audio_not_ready', 'Playback must refer to an audited ready audio request.')
            binding = {k: ready[0].get(k) for k in BINDING_FIELDS}
            if any({k: r.get(k) for k in BINDING_FIELDS} != binding for r in ready):
                raise APIError(409, 'ambiguous_audio_request', 'Audio request ID has inconsistent bindings.')
            earlier = [r['report'] for r in previous if r.get('audio_request_id') == data['audio_request_id']]
            started = any(r['event'] == 'started' for r in earlier)
            terminal = any(r['event'] in ('stopped', 'completed', 'failed') for r in earlier)
            if terminal or (data['event'] == 'started' and started) or (data['event'] in ('stopped', 'completed') and not started):
                raise APIError(409, 'playback_sequence', 'Playback reports must have one start and one terminal event.')
            duration = binding['audio_duration_seconds']
            if data['event'] == 'started' and (data['position_seconds'] != 0 or data['elapsed_seconds'] != 0):
                raise APIError(400, 'invalid_playback_timing', 'Start must begin at zero.')
            if not isinstance(duration, (int, float)) or data['position_seconds'] > duration + .1:
                raise APIError(400, 'invalid_playback_timing', 'Playback position exceeds the prepared clip.')
            if data['event'] == 'completed' and (data['position_seconds'] < max(0, duration - .1) or data['elapsed_seconds'] < max(0, duration - .25)):
                raise APIError(400, 'invalid_playback_completion', 'Completion must report the end of the clip.')
            if earlier and data['elapsed_seconds'] < earlier[-1]['elapsed_seconds']:
                raise APIError(400, 'invalid_playback_timing', 'Playback elapsed time must not move backwards.')
            record = {**{k: ready[0][k] for k in IDENTITY_FIELDS if k in ready[0]}, **binding,
                      'event': 'playback_report', 'playback_schema_version': 'tutor-playback-v1',
                      'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'monotonic_seconds': time.monotonic(),
                      'receipt_run_id': app.run_id,
                      'evidence_source': 'client_reported_not_verified_hearing', 'report': dict(data)}
            from tutor_dialogue_log import annotate
            annotate(record)
            try:
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                raise APIError(503, 'playback_audit_unavailable', 'Playback report could not be recorded.')
            return {'recorded': True, 'event_id': data['event_id'], 'idempotent_replay': False}
