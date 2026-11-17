"""Explicit synthetic PCM markers, NOT real ASR; no credentials/provider calls."""
from pathlib import Path
import io
import struct
import sys
import time
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture


class SpeechFixture:
    def transcribe(self, audio):
        with wave.open(io.BytesIO(audio)) as wav:
            sample = struct.unpack('<h', wav.readframes(1))[0]
        time.sleep(1.5 if sample > 16000 else .1)
        return {'text': 'Compare an easier explanation.' if sample == 0 else 'Yes, use the first option.'}


if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[2] / 'StudyData/macos/speech-fixture'
    server = Server(('127.0.0.1', 8772), Experiment(MockModel(), folder),
                    TutorSessions(ComparisonFixture(), folder), speech=SpeechFixture())
    print('Synthetic speech fixture on 127.0.0.1:8772; no real ASR or paid calls', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
