import io
import http.client
import json
from pathlib import Path
import sys
import struct
import threading
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech import SpeechConfig, SpeechService, SpeechError, QwenTransport, validate_wav, normalize_provider_wav
from tutor_state import DEFAULT_SETTINGS, DIALOGUE_OPTIONS, TutorState, validate_patch
from core import APIError
from tutor_voice_catalog import VOICE_PROVIDERS

def wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b'\0\0' * 100)
    return buf.getvalue()

def provider_stream_wav():
    audio = wav_bytes()
    return (audio[:4] + struct.pack('<I', 0x7fffffbf) + audio[8:40]
            + struct.pack('<I', 0x7fffff9b) + audio[44:])

class FakeTransport:
    def __init__(self):
        self.calls = []
        self.downloads = []
        self.audio = wav_bytes()
        self.asr = {'output': {'text': ' Please speak slowly. '}}
        self.cancel = None
        self.error = None
    def post(self, route, payload):
        self.calls.append((route, payload))
        if self.error:
            raise self.error
        if self.cancel:
            self.cancel.set()
        if 'multimodal' in route:
            return self.asr
        return {'output': {'audio': {'url': 'https://test.oss-cn-beijing.aliyuncs.com/sample.wav'}},
                'request_id': 'safe-id', 'usage': {'characters': 5, 'untrusted': 'secret'}}
    def download(self, url):
        self.downloads.append(url)
        return self.audio

class SpeechTests(unittest.TestCase):
    def setUp(self):
        self.config = SpeechConfig('https://test.cn-beijing.maas.aliyuncs.com', 'test-secret')
        self.fake = FakeTransport()
        self.service = SpeechService(self.config, self.fake)
        self.settings = dict(DEFAULT_SETTINGS)

    def test_five_selected_voices_and_default(self):
        self.assertEqual(DIALOGUE_OPTIONS['voice'], ('voice_a', 'voice_b', 'voice_c', 'voice_d', 'voice_e'))
        self.assertEqual(TutorState().snapshot()['settings']['voice'], 'voice_d')
        self.assertEqual(VOICE_PROVIDERS['voice_d'], 'qwen-audio-3.0-tts-plus-loongadriangao')
        self.assertEqual(VOICE_PROVIDERS['voice_a'], 'longanlingxin')
        for voice in DIALOGUE_OPTIONS['voice']:
            self.assertEqual(validate_patch({'voice': voice})['voice'], voice)
        for voice in ('voice_x', 'voice_y', 'voice_z'):
            with self.assertRaises(APIError): validate_patch({'voice': voice})

    def test_provider_voice_mapping_all_five(self):
        for voice, provider in VOICE_PROVIDERS.items():
            result = self.service.synthesize('Hello.', {**self.settings, 'voice': voice})
            self.assertEqual(self.fake.calls[-1][1]['input']['voice'], provider)
            self.assertEqual(result['settings']['voice'], voice)
        self.assertEqual(len(self.fake.calls), 5)

    def test_cache_isolation_and_no_extra_call_on_replay(self):
        first = self.service.synthesize('Hello.', self.settings)
        replay = self.service.synthesize('Hello.', self.settings)
        self.assertFalse(first['cache_hit']); self.assertTrue(replay['cache_hit'])
        for change in ({'voice': 'voice_a'}, {'tone': 'friendly'}, {'speech_rate': .7}):
            self.assertFalse(self.service.synthesize('Hello.', {**self.settings, **change})['cache_hit'])
        self.service.synthesize('Other text.', self.settings)
        self.assertEqual(len(self.fake.calls), 5)

    def test_snapshot_and_cache_results_are_detached(self):
        result = self.service.synthesize('Hello.', self.settings)
        result['settings']['voice'] = 'voice_e'
        self.settings['voice'] = 'voice_a'
        cached = self.service.synthesize('Hello.', dict(DEFAULT_SETTINGS))
        self.assertEqual(cached['settings']['voice'], 'voice_d')
        self.assertNotIn('untrusted', cached['usage'])
        self.assertNotIn('url', cached)

    def test_length_and_appearance_do_not_change_identical_audio(self):
        self.service.synthesize('Hello.', self.settings)
        result = self.service.synthesize('Hello.', {**self.settings, 'reply_length': 'brief', 'jacket_color': 'red'})
        self.assertTrue(result['cache_hit'])
        self.assertEqual(len(self.fake.calls), 1)

    def test_bounded_cache_eviction_and_clear(self):
        service = SpeechService(self.config, self.fake, cache_entries=1)
        for text in ('one', 'two', 'one'): service.synthesize(text, self.settings)
        self.assertEqual(len(self.fake.calls), 3)
        service.clear_cache(); service.synthesize('one', self.settings)
        self.assertEqual(len(self.fake.calls), 4)

    def test_zero_byte_cache_retains_nothing(self):
        service = SpeechService(self.config, self.fake, cache_bytes=0)
        for _ in range(2): service.synthesize('Hello.', self.settings)
        self.assertEqual(len(self.fake.calls), 2)

    def test_cancel_before_call_does_not_spend(self):
        event = threading.Event(); event.set()
        with self.assertRaisesRegex(SpeechError, 'cancelled'):
            self.service.synthesize('Hello.', self.settings, cancel=event)
        with self.assertRaisesRegex(SpeechError, 'cancelled'):
            self.service.transcribe(wav_bytes(), cancel=event)
        self.assertEqual(self.fake.calls, [])

    def test_cancel_after_provider_skips_download_and_cache(self):
        event = threading.Event(); self.fake.cancel = event
        with self.assertRaisesRegex(SpeechError, 'cancelled'):
            self.service.synthesize('Hello.', self.settings, cancel=event)
        self.assertEqual(self.fake.downloads, [])
        self.fake.cancel = None; event.clear()
        self.assertFalse(self.service.synthesize('Hello.', self.settings)['cache_hit'])

    def test_concurrent_identical_synthesis_calls_once(self):
        results = []
        workers = [threading.Thread(target=lambda: results.append(self.service.synthesize('Hello.', self.settings))) for _ in range(4)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(timeout=3)
        self.assertEqual(len(results), 4); self.assertEqual(len(self.fake.calls), 1)

    def test_http_error_has_no_automatic_retry(self):
        self.fake.error = SpeechError('provider_http_error', 429)
        with self.assertRaises(SpeechError): self.service.synthesize('Hello.', self.settings)
        self.assertEqual(len(self.fake.calls), 1)

    def test_corrupt_audio_not_cached(self):
        self.fake.audio = b'invalid'
        with self.assertRaises(SpeechError): self.service.synthesize('Hello.', self.settings)
        self.fake.audio = wav_bytes()
        self.assertFalse(self.service.synthesize('Hello.', self.settings)['cache_hit'])

    def test_invalid_request_before_provider(self):
        for text, settings in [('', self.settings), ('a' * 8001, self.settings), ('Hi', {}), ('Hi', {**self.settings, 'voice': 'voice_z'}), ('Hi', {**self.settings, 'speech_rate': 1.31})]:
            with self.assertRaises((SpeechError, APIError)): self.service.synthesize(text, settings)
        self.assertEqual(self.fake.calls, [])

    def test_transcript_text_only_and_english_payload(self):
        result = self.service.transcribe(wav_bytes())
        self.assertEqual(result['text'], 'Please speak slowly.')
        route, payload = self.fake.calls[0]
        self.assertEqual(payload['parameters']['language_hints'], ['en'])
        self.assertTrue(payload['input']['messages'][0]['content'][0]['input_audio']['data'].startswith('data:audio/wav;base64,'))
        self.assertNotIn('audio', result)
        self.assertEqual(len(self.service._cache), 0)

    def test_empty_transcript_is_not_submitted(self):
        self.fake.asr = {'output': {'text': '  '}}
        with self.assertRaisesRegex(SpeechError, 'no_speech'): self.service.transcribe(wav_bytes())

    def test_sentence_shape_supported_but_malformed_rejected(self):
        self.fake.asr = {'output': {'sentence': {'text': 'Hello'}}}
        self.assertEqual(self.service.transcribe(wav_bytes())['text'], 'Hello')
        self.fake.asr = {'output': []}
        with self.assertRaisesRegex(SpeechError, 'invalid_transcript'): self.service.transcribe(wav_bytes())

    def test_invalid_wav_and_truncation_rejected(self):
        for value in (b'', wav_bytes()[:-8], b'x' * (8_000_001)):
            with self.assertRaises(SpeechError): self.service.transcribe(value)
        self.assertEqual(self.fake.calls, [])

    def test_provider_stream_header_normalized_before_cache_and_duration(self):
        self.fake.audio = provider_stream_wav()
        first = self.service.synthesize('Hello.', self.settings)
        self.assertEqual(first['audio'], wav_bytes())
        self.assertEqual(first['audio'][44:], self.fake.audio[44:])
        with wave.open(io.BytesIO(first['audio'])) as wav:
            self.assertEqual(wav.getnframes(), 100)
        cached = self.service.synthesize('Hello.', self.settings)
        self.assertTrue(cached['cache_hit'])
        self.assertEqual(cached['audio'], first['audio'])
        self.assertEqual(len(self.fake.calls), 1)

    def test_stream_header_not_accepted_for_participant_input(self):
        with self.assertRaises(SpeechError): self.service.transcribe(provider_stream_wav())
        self.assertEqual(self.fake.calls, [])

    def test_normalization_leaves_standard_wav_unchanged(self):
        audio = wav_bytes()
        self.assertEqual(normalize_provider_wav(audio), audio)

    def test_normalization_rejects_truncated_and_unknown_stream_formats(self):
        stream = provider_stream_wav()
        unknown = bytearray(stream); struct.pack_into('<I', unknown, 40, 0x7fffff9a)
        bad_format = bytearray(stream); struct.pack_into('<I', bad_format, 28, 1)
        for audio in (wav_bytes()[:-8], stream[:-1], stream[:44], bytes(unknown), bytes(bad_format)):
            with self.subTest(size=len(audio)):
                with self.assertRaises(SpeechError): normalize_provider_wav(audio)

    def test_transport_rejects_incomplete_http_body_without_retry(self):
        transport = QwenTransport(self.config)
        response = MagicMock()
        response.__enter__.return_value = response
        response.getheader.return_value = '200'
        response.read.return_value = b'partial'
        with patch.object(transport.client, 'open', return_value=response) as opened:
            with self.assertRaisesRegex(SpeechError, 'provider_incomplete_response'):
                transport.download('https://test.oss-cn-beijing.aliyuncs.com/audio')
            self.assertEqual(opened.call_count, 1)

    def test_transport_incomplete_chunked_body_redacts_partial_content(self):
        transport = QwenTransport(self.config)
        response = MagicMock()
        response.__enter__.return_value = response
        response.getheader.return_value = None
        response.read.side_effect = http.client.IncompleteRead(b'secret-audio', 100)
        with patch.object(transport.client, 'open', return_value=response):
            with self.assertRaisesRegex(SpeechError, '^provider_connection_error$'):
                transport.download('https://test.oss-cn-beijing.aliyuncs.com/audio')

    def test_configuration_and_key_redaction(self):
        self.assertNotIn('test-secret', repr(self.config))
        for url in ('http://test.cn-beijing.maas.aliyuncs.com', 'https://attacker.example', 'https://test.cn-beijing.maas.aliyuncs.com/redirect'):
            with self.assertRaises(ValueError): SpeechConfig(url, 'secret')
        with self.assertRaises(ValueError): SpeechConfig(self.config.base_url, 'secret', timeout=float('nan'))

    def test_download_upgrades_https_without_authorization(self):
        transport = QwenTransport(self.config)
        with patch.object(transport, '_read', return_value=wav_bytes()) as read:
            transport.download('http://test.oss-cn-beijing.aliyuncs.com/audio?signature=test')
            request = read.call_args.args[0]
            self.assertTrue(request.full_url.startswith('https://'))
            self.assertIsNone(request.get_header('Authorization'))
            for url in ('https://evil.example/audio', 'http://127.0.0.1/audio', 'https://x.aliyuncs.com@evil.example/a', 'https://x.aliyuncs.com:80/a'):
                with self.assertRaises(SpeechError): transport.download(url)

    def test_transport_http_errors_redact_provider_body(self):
        transport = QwenTransport(self.config)
        with patch.object(transport.client, 'open', side_effect=urllib.error.HTTPError('secret-url', 401, 'test-secret', {}, None)):
            with self.assertRaises(SpeechError) as error: transport.post('/test', {})
        self.assertEqual(error.exception.status, 401)
        self.assertNotIn('secret', str(error.exception))

    def test_unity_catalog_matches_backend(self):
        path = Path(__file__).resolve().parents[2] / 'Assets/Project/Scripts/Tutor/TutorClient.cs'
        source = path.read_text().split('public static readonly string[] Ids = {', 1)[1].split('};', 1)[0]
        self.assertEqual(tuple(__import__('re').findall(r'"(voice_\w)"', source)), DIALOGUE_OPTIONS['voice'])

if __name__ == '__main__': unittest.main()
