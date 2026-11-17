"""Synthetic silent WAV through the real speech cache; no provider/credentials."""
import io
from pathlib import Path
import sys
import time
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server, Handler
from speech import SpeechConfig, SpeechService, SpeechError
from tutor_session import TutorSessions
from test_speech import FakeTransport
from unity_comparison_fixture_server import ComparisonFixture
from unity_speech_fixture_server import SpeechFixture
from tutor_voice_catalog import VOICE_PROVIDERS


class AudioTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
            wav.writeframes(b'\0\0' * (24000 * 8))
        self.audio = buf.getvalue()

    def post(self, route, payload):
        voice = payload.get('input', {}).get('voice')
        time.sleep(1.5 if voice == VOICE_PROVIDERS['voice_c'] else .1)
        if voice == VOICE_PROVIDERS['voice_e']: raise SpeechError('fixture_failure')
        return super().post(route, payload)


class AudioFixture(SpeechService):
    def transcribe(self, audio, **kwargs): return SpeechFixture().transcribe(audio)


if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[2] / 'StudyData/macos/audio-fixture'
    transport = AudioTransport()
    speech = AudioFixture(SpeechConfig('https://fixture.cn-beijing.maas.aliyuncs.com', 'fixture-not-a-key'), transport)
    class FixtureHandler(Handler):
        def do_GET(self):
            if self.path == '/fixture/tts-count': return self.send_json(200, {'calls': len(transport.calls)})
            super().do_GET()
    server = Server(('127.0.0.1', 8773), Experiment(MockModel(), folder), TutorSessions(ComparisonFixture(), folder), speech=speech)
    server.RequestHandlerClass = FixtureHandler
    print('Silent audio fixture on 127.0.0.1:8773; Voice C delayed, Voice E fails; no paid calls', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
