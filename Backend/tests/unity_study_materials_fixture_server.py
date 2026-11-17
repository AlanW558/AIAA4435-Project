"""32-task engineering preview. Synthetic silent TTS; no cloud or microphone."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture
from test_speech import wav_bytes
class Speech:
    def synthesize(self,text,settings):return {'audio':wav_bytes(),'cache_hit':False}
if __name__=='__main__':
    folder=Path(__file__).resolve().parents[2]/'StudyData/macos/study-materials-fixture'
    server=Server(('127.0.0.1',8778),Experiment(MockModel(),folder),TutorSessions(ComparisonFixture(),folder),speech=Speech())
    print('Study materials fixture localhost:8778; synthetic audio; no providers',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
