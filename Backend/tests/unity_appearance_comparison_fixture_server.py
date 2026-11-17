"""Explicit local appearance comparison fixture; never a study/live backend."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import MockModel, ModelError
from server import Server
from tutor_session import TutorSessions
from test_tutor_generation import GenerationFixture
from test_tutor_multidomain import proposal


class AppearanceComparisonFixture(GenerationFixture):
    model = "unity-appearance-comparison-fixture"

    def interpret_tutor(self, context):
        query = context["query"]
        cases = {
            "Compare a casual look.": proposal({"outfit": "sport"}, {"accessory": "none"}, required=[]),
            "Make it green and slightly larger.": proposal({"jacket_color": "green", "scale": 1.05}),
            "Switch to Nailong.": proposal({"avatar_id": "nailong"}),
        }
        if query not in cases:
            raise ModelError("Unknown explicit appearance fixture request")
        return self._return("interpret", context, cases[query])


if __name__ == "__main__":
    folder = Path(__file__).resolve().parents[2] / "StudyData/macos/appearance-comparison-fixture"
    server = Server(("127.0.0.1", 8770), Experiment(MockModel(), folder), TutorSessions(AppearanceComparisonFixture(), folder))
    print("Explicit appearance fixture on 127.0.0.1:8770; no paid calls", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
