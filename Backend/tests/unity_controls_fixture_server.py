"""Explicit panel fixtures; no provider calls. Deliberately lose one control response."""
from pathlib import Path
import socket
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server, Handler
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture
from test_tutor_multidomain import proposal


class ControlsFixture(ComparisonFixture):
    model = "unity-controls-fixture"

    def interpret_tutor(self, context):
        q = context["query"]
        if q == "Make it green and slightly larger.":
            return self._return("interpret", context, proposal({"jacket_color": "green", "scale": 1.05}))
        if q == "For the next answer only, use encouraging wording and Voice B.":
            return self._return("interpret", context, proposal({"tone": "encouraging", "voice": "voice_b"}, scope="turn"))
        return super().interpret_tutor(context)


class ControlsHandler(Handler):
    lost = False

    def send_json(self, status, data):
        if self.command == "POST" and self.path.startswith("/tutor/comparisons/") and self.path.endswith("/settings") and 200 <= status < 300 and not self.lost:
            type(self).lost = True
            self.close_connection = True
            try: self.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.connection.close()
            return
        super().send_json(status, data)


if __name__ == "__main__":
    folder = Path(__file__).resolve().parents[2] / "StudyData/macos/controls-fixture"
    server = Server(("127.0.0.1", 8771), Experiment(MockModel(), folder), TutorSessions(ControlsFixture(), folder))
    server.RequestHandlerClass = ControlsHandler
    print("Explicit panel fixture on 127.0.0.1:8771; no paid calls", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
