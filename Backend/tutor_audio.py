"""Authoritative, visibility-gated TTS. Clients provide IDs, never text/settings."""
from copy import deepcopy
import hashlib
import io
import wave

from core import APIError, IDENTIFIER
from speech import SpeechError, validate_wav
from tutor_voice_catalog import SAMPLE_TEXT
from tutor_study_materials import audio_material
from tutor_state import DEFAULT_SETTINGS


class TutorAudio:
    def __init__(self, tutor, comparisons, speech=None):
        self.tutor, self.comparisons, self.speech = tutor, comparisons, speech

    @property
    def available(self):
        return callable(getattr(self.speech, 'synthesize', None))

    def resolve(self, kind, identifier, data):
        expected = {'request_id', 'expected_revision', 'condition', 'purpose', 'exchange_id'}
        if data.get('purpose') == 'clarification':
            expected.add('question_id')
        if set(data) != expected:
            raise APIError(400, 'invalid_audio_request', 'Send only the audio target and its context.')
        if not isinstance(data['request_id'], str) or not IDENTIFIER.fullmatch(data['request_id']):
            raise APIError(400, 'invalid_request_id', 'Use a valid audio request ID.')
        if data['purpose'] not in ('sample', 'reply', 'material', 'clarification') or type(data['exchange_id']) is not int:
            raise APIError(400, 'invalid_audio_target', 'Choose a recorded tutor reply or current clarification.')
        if data['purpose'] == 'clarification' and (kind != 'sessions' or data['exchange_id'] != 0 or not isinstance(data['question_id'], str) or not IDENTIFIER.fullmatch(data['question_id'])):
            raise APIError(400, 'invalid_audio_target', 'Clarification speech belongs to the current natural conversation only.')
        app = self.comparisons if kind == 'comparisons' else self.tutor
        target = app.get(identifier)
        with target.lock:
            view = app.view(target)
            if type(data['expected_revision']) is not int or data['expected_revision'] != view['revision']:
                raise APIError(409, 'stale_audio_context', 'Audio context changed. Refresh before playing.')
            if kind == 'comparisons':
                if view['lifecycle'] != 'active' or view['phase'] == 'closed' or data['condition'] != view['selected_condition']:
                    raise APIError(409, 'audio_unavailable', 'Audio is unavailable in this task or selection.')
                # Even samples cannot disclose unrevealed branch settings. Only the
                # pre-task baseline or a settled, fully revealed branch is eligible.
                branch = view['branches'][view['selected_condition']]
                initial = view['phase'] == 'awaiting_input'
                ready = view['results_visible'] and branch['status'] in ('ready', 'stopped')
                if not ready and not (initial and data['purpose'] in ('sample', 'material')):
                    raise APIError(409, 'audio_hidden', 'Wait for all required clarifications and results.')
                snapshot = view['baseline'] if initial else branch['result']['state']
            else:
                if data['condition'] != view['condition'] or (view.get('question') and data['purpose'] != 'clarification') or any(j['status'] == 'queued' for j in view['generation_jobs']):
                    raise APIError(409, 'audio_unavailable', 'Finish the current interaction before playing audio.')
                snapshot = view
            if data['purpose'] == 'clarification':
                question = view.get('question')
                if not question or question['question_id'] != data['question_id']:
                    raise APIError(409, 'stale_question', 'This clarification is no longer active.')
                text, settings = question['text'], snapshot['settings']
                choices = [o['label'] for o in question.get('options', []) if o['id'] not in ('other', 'cancel')]
                if choices:
                    text += (' The proposed choice is: ' if len(choices) == 1 else ' The choices are: ') + '; or '.join(choices) + '.'
            elif data['purpose'] == 'material':
                if kind != 'comparisons':
                    raise APIError(400, 'invalid_material', 'Listening materials belong to registered study tasks.')
                material = audio_material(target.sequence, target.comparison.task_code, data['exchange_id'])
                text, settings = material['text'], {**DEFAULT_SETTINGS, **material['settings']}
            elif data['purpose'] == 'sample':
                if data['exchange_id'] != 0:
                    raise APIError(400, 'invalid_audio_target', 'Samples do not have an exchange ID.')
                text, settings = SAMPLE_TEXT, snapshot['settings']
            else:
                exchange = next((e for e in snapshot['conversation'] if e['id'] == data['exchange_id']), None)
                if not exchange:
                    raise APIError(404, 'reply_not_found', 'Choose a reply in the current visible conversation.')
                text = '\n'.join(m['content'] for m in exchange['messages'] if m['role'] == 'assistant')
                settings = exchange['settings']
            return target, text, deepcopy(settings)

    def log(self, kind, target, event, **payload):
        if kind == 'comparisons': self.comparisons._log(target, event, **payload)
        else: self.tutor.log(target, event, **payload)

    def synthesize(self, kind, identifier, data):
        if not self.available:
            raise APIError(503, 'audio_unconfigured', 'Speech playback is not enabled on this backend.')
        target, text, settings = self.resolve(kind, identifier, data)
        app = self.comparisons if kind == 'comparisons' else self.tutor
        view = app.view(target)
        branch = view['branches'][data['condition']] if kind == 'comparisons' else None
        snapshot = ((branch or {}).get('result') or {}).get('state') or view.get('baseline', view)
        meta = {'audio_request_id': data['request_id'], 'condition': data['condition'], 'purpose': data['purpose'],
                'exchange_id': data['exchange_id'], 'expected_revision': data['expected_revision'],
                'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'speech_settings': {k: settings[k] for k in ('voice', 'tone', 'speech_rate')}}
        if data['purpose'] == 'clarification':
            meta['question_id'] = data['question_id']
        meta.update(branch_revision=branch['branch_revision'] if branch else None,
                    settings_scope='study_material' if data['purpose'] == 'material' else 'shared_preparation' if kind == 'comparisons' and view.get('preparation_required') and not view.get('preparation_confirmed') else 'task_baseline' if kind == 'comparisons' and view['phase'] == 'awaiting_input' else 'branch',
                    state_revision=snapshot.get('state_revision', snapshot.get('revision')),
                    reveal_id=(view.get('first_reveal') or {}).get('reveal_id'))
        self.log(kind, target, 'audio_requested', **meta)
        try:
            rendered = self.speech.synthesize(text, settings)
            validate_wav(rendered['audio'])
            # State may change while the provider works or while waiting for cache.
            self.resolve(kind, identifier, data)
        except SpeechError as exc:
            self.log(kind, target, 'audio_failed', error=exc.code, **meta)
            raise APIError(502, 'audio_failed', 'Speech synthesis failed. You may try again.') from None
        except APIError:
            self.log(kind, target, 'audio_discarded', **meta)
            raise
        with wave.open(io.BytesIO(rendered['audio']), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
        self.log(kind, target, 'audio_ready', cache_hit=bool(rendered.get('cache_hit')), audio_duration_seconds=duration, **meta)
        return rendered['audio']
