"""Questionnaire fixture: synthetic STT and one lost feedback ACK, no providers."""
from pathlib import Path
import sys
import socket
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server, Handler
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture

class Speech:
    def transcribe(self, audio):
        time.sleep(.5)
        return {'text': 'The clarification helped me express my preference.'}

class FixtureHandler(Handler):
    lost = False
    def send_json(self, status, data):
        if self.command == 'POST' and self.path.endswith('/feedback') and 200 <= status < 300 and not type(self).lost:
            type(self).lost = True
            self.close_connection = True
            try: self.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.connection.close()
            return
        super().send_json(status, data)

if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[2] / 'StudyData/macos/questionnaire-fixture'
    server = Server(('127.0.0.1', 8776), Experiment(MockModel(), folder), TutorSessions(ComparisonFixture(), folder), speech=Speech())
    server.RequestHandlerClass = FixtureHandler
    print('Questionnaire fixture 127.0.0.1:8776; synthetic STT, one lost feedback ACK; no providers', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
