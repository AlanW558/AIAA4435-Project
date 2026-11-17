"""Session-bound STT. Audio is transient; only fingerprints/text are memoized.

No automatic dialogue mutation and no provider retry. Request IDs remain reserved
until server restart, including failures, so a lost HTTP response cannot bill twice.
"""
import base64
import binascii
import hashlib
import threading

from core import APIError, IDENTIFIER
from speech import SpeechError, MAX_AUDIO, validate_wav


class TutorTranscription:
    def __init__(self, tutor, comparisons, speech=None, limit=4096):
        self.tutor, self.comparisons, self.speech = tutor, comparisons, speech
        self.limit, self.entries, self.lock = limit, {}, threading.Lock()

    def check_context(self, kind, identifier, data):
        app = self.comparisons if kind in ('comparisons', 'survey', 'preference') else self.tutor
        view = app.view(app.get(identifier))
        valid = type(data.get('expected_revision')) is int and view['revision'] == data['expected_revision']
        if kind == 'preference':
            sequence = view.get('sequence', {})
            valid = (type(data.get('expected_revision')) is int
                     and sequence.get('preference_revision') == data['expected_revision']
                     and sequence.get('preference_scope') == data.get('condition')
                     and data.get('condition') in ('attribute', 'comparison_overall')
                     and not sequence.get('preference_paused') and not sequence.get('preference_exited')
                     and not view.get('next_task_id') and view['lifecycle'] == 'submitted'
                     and data.get('question_id', '') == '')
            question = {}
        elif kind == 'survey':
            condition = data.get('condition')
            branch = view['branches'].get(condition, {})
            valid = (type(data.get('expected_revision')) is int
                     and branch.get('branch_revision') == data['expected_revision']
                     and view['feedback_version'] == 'attribute-feedback-v2'
                     and view['lifecycle'] == 'active' and view['results_visible']
                     and condition == view['selected_condition']
                     and branch.get('status') in ('ready', 'stopped')
                     and data.get('question_id', '') == '')
            question = {}
        elif kind == 'comparisons':
            condition = data.get('condition')
            branch = view['branches'].get(condition, {})
            question = branch.get('question') or {}
            valid = valid and view['lifecycle'] == 'active' and view['phase'] != 'closed'
            valid = valid and (not view.get('preparation_required') or view.get('preparation_confirmed'))
            valid = valid and condition == view['selected_condition']
            valid = valid and (view['phase'] == 'awaiting_input' or branch.get('status') == 'awaiting_clarification'
                              or view['results_visible'] and branch.get('status') in ('ready', 'stopped'))
        else:
            question = view.get('question') or {}
            valid = valid and data.get('condition') == view['condition']
        valid = valid and data.get('question_id', '') == question.get('question_id', '')
        if not valid:
            raise APIError(409, 'stale_speech_context', 'Input context changed. Record again in the current task.')

    def transcribe(self, kind, identifier, data):
        if self.speech is None:
            raise APIError(503, 'speech_unconfigured', 'Speech recognition is not enabled on this backend.')
        rid = data.get('request_id')
        if not isinstance(rid, str) or not IDENTIFIER.fullmatch(rid):
            raise APIError(400, 'invalid_request_id', 'Use a valid speech request ID.')
        try:
            encoded = data.get('audio_base64')
            if not isinstance(encoded, str) or len(encoded) > (MAX_AUDIO + 2) // 3 * 4:
                raise ValueError()
            audio = base64.b64decode(encoded, validate=True)
            validate_wav(audio, participant=True)
        except (ValueError, binascii.Error, SpeechError):
            raise APIError(400, 'invalid_audio', 'Use a nonempty mono PCM16 WAV, at most 120 seconds.')
        fingerprint = (hashlib.sha256(audio).hexdigest(), data.get('expected_revision'), data.get('condition'), data.get('question_id', ''))
        key = (kind, identifier, rid)
        # Serializing ASR also bounds provider concurrency. Never hold a session
        # lock over a network call: pause/close must remain responsive.
        with self.lock:
            self.check_context(kind, identifier, data)
            existing = self.entries.get(key)
            if existing:
                if existing[0] != fingerprint:
                    raise APIError(409, 'speech_request_conflict', 'Speech request ID was already used.')
                outcome = existing[1]
            else:
                if len(self.entries) >= self.limit:
                    raise APIError(503, 'speech_capacity', 'Speech request capacity reached. Restart between study sessions.')
                # Reserve before invoking the provider, including unexpected errors.
                outcome = APIError(502, 'speech_failed', 'Recognition failed. Record again when ready.')
                self.entries[key] = (fingerprint, outcome)
                try:
                    result = self.speech.transcribe(audio)
                    outcome = {'text': result['text'], 'request_id': rid}
                except SpeechError as exc:
                    outcome = APIError(502, exc.code, 'Recognition failed. Record again when ready.')
                finally:
                    self.entries[key] = (fingerprint, outcome)
            self.check_context(kind, identifier, data)
            if isinstance(outcome, APIError):
                raise outcome
            return dict(outcome)
