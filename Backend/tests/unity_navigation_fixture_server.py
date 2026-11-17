"""Explicit local task-navigation test with lost acknowledgements. No providers."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture, LostResponseHandler

if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[2] / 'StudyData/macos/navigation-fixture'
    server = Server(('127.0.0.1', 8775), Experiment(MockModel(), folder), TutorSessions(ComparisonFixture(), folder))
    server.RequestHandlerClass = LostResponseHandler
    print('Task navigation fixture on 127.0.0.1:8775; lost create/start/answer/submit/next ACKs; no providers', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
