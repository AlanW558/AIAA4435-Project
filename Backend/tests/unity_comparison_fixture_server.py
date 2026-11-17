"""Explicit local comparison fixtures, including lost POST responses; never for study use."""
from pathlib import Path
import socket
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel
from server import Server, Handler
from tutor_session import TutorSessions
from unity_fixture_server import UnityFixture
from test_tutor_interpretation import tailoring


class ComparisonFixture(UnityFixture):
    model = "unity-comparison-fixture"

    def interpret_tutor(self, context):
        if context["query"] == "Compare an easier explanation.":
            return self._return("interpret", context, tailoring("brief", "detailed", kind="mixed", conversation_query="What is active recall?"))
        return super().interpret_tutor(context)


class LostResponseHandler(Handler):
    lost = set()

    def send_json(self, status, data):
        # Apply the real operation, then drop its first successful response.
        key = "create" if self.path == "/tutor/comparisons" else next((op for op in ("start", "answer", "submit", "next") if self.path.endswith("/" + op)), None)
        if self.command == "POST" and key and 200 <= status < 300 and key not in self.lost:
            self.lost.add(key)
            self.close_connection = True
            try: self.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.connection.close()
            return
        super().send_json(status, data)


if __name__ == "__main__":
    logs = Path(__file__).resolve().parents[2] / "StudyData/macos/comparison-fixture"
    server = Server(("127.0.0.1", 8768), Experiment(MockModel(), logs), TutorSessions(ComparisonFixture(), logs))
    server.RequestHandlerClass = LostResponseHandler
    print("Explicit comparison fixture on 127.0.0.1:8768; lost create/start/answer/submit/next responses; no paid calls", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
