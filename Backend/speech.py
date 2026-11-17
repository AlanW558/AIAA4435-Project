"""Internal STT/TTS boundary. No HTTP routes, participant recordings or disk cache.

Cancellation is cooperative between network operations; an in-flight call may be
billed and runs until its bounded timeout. Nothing retries or switches providers.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
import base64
import hashlib
import http.client
import io
import json
import math
import os
import re
import struct
import threading
import urllib.error
import urllib.parse
import urllib.request
import wave

from tutor_state import validate_patch
from tutor_voice_catalog import VOICE_PROVIDERS, TONE_INSTRUCTIONS, FIXED_PARAMETERS, PROFILE_VERSION

MAX_AUDIO = 8_000_000

class SpeechError(Exception):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)  # Never include provider bodies, URLs, or credentials.

def check_cancel(event):
    if event is not None and event.is_set():
        raise SpeechError('cancelled')

def validate_wav(audio, *, participant=False):
    if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_AUDIO:
        raise SpeechError('invalid_audio')
    try:
        with wave.open(io.BytesIO(audio)) as wav:
            frames, channels, width, rate = wav.getnframes(), wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            if channels != 1 or width != 2 or rate not in (16000, 24000, 48000) or frames < 1:
                raise SpeechError('invalid_audio_format')
            if participant and frames > rate * 120:
                raise SpeechError('recording_too_long')
            if len(wav.readframes(frames)) != frames * channels * width:
                raise SpeechError('truncated_audio')
    except (wave.Error, EOFError, ValueError):
        raise SpeechError('invalid_audio') from None

def normalize_provider_wav(audio):
    """Canonicalize the exact streaming header observed in Qwen TTS downloads.

    Only provider output enters here. Participant input remains strictly checked.
    These headers have no final frame count: a successful HTTP body read is the
    transport completeness boundary, not evidence of perceptual completeness.
    Arbitrary oversized declarations must never be silently repaired.
    """
    if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_AUDIO:
        raise SpeechError('invalid_audio')
    if (audio[:4] == b'RIFF' and audio[4:8] == struct.pack('<I', 0x7fffffbf)
            and audio[8:20] == b'WAVEfmt \x10\x00\x00\x00'
            and audio[36:44] == b'data' + struct.pack('<I', 0x7fffff9b)):
        encoding, channels, rate, byte_rate, align, bits = struct.unpack('<HHIIHH', audio[20:36])
        if ((encoding, channels, align, bits) != (1, 1, 2, 16)
                or rate not in (16000, 24000, 48000) or byte_rate != rate * 2
                or len(audio) == 44 or (len(audio) - 44) % 2):
            raise SpeechError('invalid_audio_format')
        audio = (audio[:4] + struct.pack('<I', len(audio) - 8) + audio[8:40]
                 + struct.pack('<I', len(audio) - 44) + audio[44:])
    validate_wav(audio)
    return audio

@dataclass(frozen=True)
class SpeechConfig:
    base_url: str
    api_key: str = field(repr=False)
    asr_model: str = 'qwen-audio-3.0-asr-flash'
    tts_model: str = 'qwen-audio-3.0-tts-plus'
    timeout: float = 30.0

    def __post_init__(self):
        # Only the selected provider receives this credential; no redirects.
        if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.(cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com', self.base_url):
            raise ValueError('Configure an official workspace-specific Qwen HTTPS base URL.')
        if not self.api_key or not self.asr_model or not self.tts_model:
            raise ValueError('Speech credentials and model IDs must be configured explicitly.')
        if isinstance(self.timeout, bool) or not math.isfinite(self.timeout) or not 1 <= self.timeout <= 60:
            raise ValueError('Speech timeout must be 1–60 seconds.')

    @classmethod
    def from_env(cls):
        return cls(os.environ.get('QWEN_BASE_URL', '').rstrip('/'),
                   os.environ.get('QWEN_API_KEY', ''),
                   os.environ.get('QWEN_ASR_MODEL', 'qwen-audio-3.0-asr-flash'),
                   os.environ.get('QWEN_TTS_MODEL', 'qwen-audio-3.0-tts-plus'),
                   float(os.environ.get('QWEN_TIMEOUT_SECONDS', '30')))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class QwenTransport:
    def __init__(self, config):
        self.config = config
        self.client = urllib.request.build_opener(NoRedirect)

    def _read(self, request, limit):
        try:
            with self.client.open(request, timeout=self.config.timeout) as response:
                declared_length = response.getheader('Content-Length')
                data = response.read(limit + 1)
            if len(data) > limit:
                raise SpeechError('provider_response_too_large')
            if declared_length is not None:
                if not declared_length.isdecimal() or int(declared_length) != len(data):
                    raise SpeechError('provider_incomplete_response')
            return data
        except urllib.error.HTTPError as exc:
            raise SpeechError('provider_http_error', exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise SpeechError('provider_connection_error') from None

    def post(self, route, payload):
        raw = self._read(urllib.request.Request(self.config.base_url + route,
            data=json.dumps(payload, allow_nan=False).encode(), method='POST',
            headers={'Authorization': 'Bearer ' + self.config.api_key, 'Content-Type': 'application/json'}), 1_000_000)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise SpeechError('invalid_provider_json') from None
        if not isinstance(data, dict):
            raise SpeechError('invalid_provider_json')
        if data.get('code'):
            raise SpeechError('provider_error')
        return data

    def download(self, url):
        if not isinstance(url, str):
            raise SpeechError('missing_audio_url')
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ''
        if (parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
                or parsed.netloc != host or not host.endswith('.aliyuncs.com')):
            raise SpeechError('invalid_audio_url')
        # Provider currently returns HTTP OSS URLs; same resource works via HTTPS.
        safe_url = parsed._replace(scheme='https').geturl()
        return self._read(urllib.request.Request(safe_url), MAX_AUDIO)

class SpeechService:
    """Immutable per-call rendering settings, bounded in-memory TTS cache.

    Internal API only: callers must enforce session/branch visibility before
    returning bytes to Unity. This module cannot expose hidden branch results.
    """
    def __init__(self, config, transport=None, *, cache_bytes=32_000_000, cache_entries=32):
        if cache_bytes < 0 or cache_entries < 0:
            raise ValueError('Cache limits must be non-negative.')
        self.config = config
        self.transport = transport if transport is not None else QwenTransport(config)
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._max_bytes, self._max_entries = cache_bytes, cache_entries
        self._lock = threading.Lock()

    def clear_cache(self):
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def _metadata(self, result):
        # Only known usage scalars and a safe request ID cross the boundary.
        request_id = result.get('request_id', '')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{0,128}', request_id):
            request_id = ''
        usage = result.get('usage', {})
        safe_usage = {}
        if isinstance(usage, dict):
            for key in ('characters', 'input_tokens', 'output_tokens', 'total_tokens', 'duration'):
                value = usage.get(key)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    safe_usage[key] = value
        return {'request_id': request_id, 'usage': safe_usage}

    def transcribe(self, audio, *, cancel=None):
        check_cancel(cancel)
        validate_wav(audio, participant=True)
        payload = {'model': self.config.asr_model, 'input': {'messages': [
            {'role': 'user', 'content': [{'type': 'input_audio', 'input_audio': {
                'data': 'data:audio/wav;base64,' + base64.b64encode(audio).decode()}}]}]},
            'parameters': {'format': 'wav', 'language_hints': ['en']}}
        response = self.transport.post('/api/v1/services/aigc/multimodal-generation/generation', payload)
        check_cancel(cancel)
        output = response.get('output', {})
        if not isinstance(output, dict):
            raise SpeechError('invalid_transcript')
        text = output.get('text')
        if text is None and isinstance(output.get('sentence'), dict):
            text = output['sentence'].get('text')
        if not isinstance(text, str) or len(text) > 8000:
            raise SpeechError('invalid_transcript')
        if not text.strip():
            raise SpeechError('no_speech')
        return {'text': text.strip(), 'model': self.config.asr_model, **self._metadata(response)}

    def synthesize(self, text, settings, *, cancel=None):
        check_cancel(cancel)
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise SpeechError('invalid_speech_text')
        if not isinstance(settings, dict) or not {'voice', 'tone', 'speech_rate'} <= settings.keys():
            raise SpeechError('missing_speech_settings')
        selected = validate_patch({k: settings[k] for k in ('voice', 'tone', 'speech_rate')})
        payload = {'model': self.config.tts_model, 'input': {
            **deepcopy(FIXED_PARAMETERS), 'text': text,
            'voice': VOICE_PROVIDERS[selected['voice']], 'rate': selected['speech_rate'],
            'instruction': TONE_INSTRUCTIONS[selected['tone']]}}
        cache_key = hashlib.sha256(json.dumps({'endpoint': self.config.base_url,
            'version': PROFILE_VERSION, 'payload': payload}, sort_keys=True).encode()).hexdigest()
        # Serializing synthesis also prevents duplicate charges for concurrent
        # identical requests. Waiting can be cancelled without taking the lock.
        while not self._lock.acquire(timeout=.05):
            check_cancel(cancel)
        try:
            check_cancel(cancel)
            if cache_key in self._cache:
                item = self._cache.pop(cache_key)
                self._cache[cache_key] = item
                return {**deepcopy(item), 'cache_hit': True}
            response = self.transport.post('/api/v1/services/audio/tts/SpeechSynthesizer', payload)
            check_cancel(cancel)
            output = response.get('output', {})
            audio_info = output.get('audio', {}) if isinstance(output, dict) else {}
            url = audio_info.get('url') if isinstance(audio_info, dict) else None
            audio = self.transport.download(url)
            check_cancel(cancel)
            audio = normalize_provider_wav(audio)
            result = {'audio': audio, 'content_type': 'audio/wav', 'settings': selected,
                'model': self.config.tts_model, 'profile_version': PROFILE_VERSION,
                'cache_key': cache_key, **self._metadata(response)}
            if self._max_entries and len(audio) <= self._max_bytes:
                while self._cache and (len(self._cache) >= self._max_entries or self._cache_bytes + len(audio) > self._max_bytes):
                    _, old = self._cache.popitem(last=False)
                    self._cache_bytes -= len(old['audio'])
                self._cache[cache_key] = deepcopy(result)
                self._cache_bytes += len(audio)
            return {**result, 'cache_hit': False}
        finally:
            self._lock.release()
