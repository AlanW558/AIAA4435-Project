"""Explicit Unity engineering fixtures; no credentials, network model or NLP fallback.

Run from repo root: python Backend/tests/unity_fixture_server.py
Only the exact test utterances below are supported. Never use for participants.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel, ModelError
from server import Server
from tutor_session import TutorSessions
from test_tutor_generation import GenerationFixture, parts
from test_tutor_interpretation import tailoring, answer
from test_tutor_session import chat


class UnityFixture(GenerationFixture):
    model = "unity-engineering-fixture"

    def __init__(self):
        super().__init__()
        self.failed_once = False

    def interpret_tutor(self, context):
        query = context["query"]
        fixtures = {
            "Use key points from now on. What is active recall?": tailoring(
                "brief", kind="mixed", conversation_query="What is active recall?"),
            "Make the explanation easier.": tailoring("brief", "detailed"),
            "Why does it help?": chat("Why does it help?"),
            "Test a recoverable generation failure.": chat("Test a recoverable generation failure."),
            "Yes, use the first option.": answer("c1"),
        }
        if query not in fixtures:
            raise ModelError("This explicit engineering fixture does not support that utterance.")
        return self._return("interpret", context, fixtures[query])

    def generate_tutor(self, context):
        if context["query"] == "Test a recoverable generation failure." and not self.failed_once:
            self.failed_once = True
            raise ModelError("Intentional engineering fixture failure; retry this job.")
        return self._return("generate", context, parts(
            "Active recall means retrieving information from memory.",
            "Retrieval practice strengthens access to what you have learned.",
            "For example, close your notes and explain the concept aloud."))


if __name__ == "__main__":
    logs = Path(__file__).resolve().parents[2] / "StudyData/macos/unity-fixture"
    server = Server(("127.0.0.1", 8766), Experiment(MockModel(), logs), TutorSessions(UnityFixture(), logs))
    print("Explicit Unity fixture listening on 127.0.0.1:8766 (no paid calls)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
