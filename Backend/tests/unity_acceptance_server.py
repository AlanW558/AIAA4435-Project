"""Local-only stage-one acceptance server; fault injection is never in production.

Default: explicit fixtures on 8767. --live: configured provider, at most 18
attempts, no automatic retries or credential fallback. No participant data.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import DeepSeekModel, ModelError
from server import Server, Handler
from tutor_session import TutorSessions
from unity_fixture_server import UnityFixture
from test_tutor_interpretation import tailoring


class AcceptanceFixture(UnityFixture):
    def interpret_tutor(self, context):
        if context["query"] == "Change your voice.":
            raw = tailoring(requested_fields=["voice"])
            raw["proposal"]["reason"] = "Voice changes are not connected yet; your settings were preserved."
            return self._return("interpret", context, raw)
        if context["query"] == "For this answer only, key points: what is active recall?":
            return self._return("interpret", context, tailoring("brief", kind="mixed", scope="turn", conversation_query="What is active recall?"))
        return super().interpret_tutor(context)


class LimitedLiveModel(DeepSeekModel):
    def __init__(self):
        super().__init__(os.environ.get("DEEPSEEK_MODEL", ""), timeout=60, max_attempts=1)
        self.fallback_key = ""
        self.attempts = 0
        self.records = []

    def _call(self, role, system, context):
        if self.attempts >= 18:
            raise ModelError("Acceptance attempt budget exhausted.")
        self.attempts += 1
        try:
            value, records = super()._call(role, system, context)
            self.records.extend(records)
            return value, records
        except ModelError as exc:
            self.records.extend(exc.records)
            raise


class AcceptanceHandler(Handler):
    def parse_body(self):
        self.received = super().parse_body()
        return self.received

    def run_request(self, method):
        if self.path == "/engineering/status" and method == "GET":
            return super().send_json(200, self.server.report())
        if self.path == "/engineering/arm" and method == "POST" and not self.server.live:
            data = self.parse_body()
            stale = data.get("fault") == "stale" and data.get("operation") == "view" and data.get("session_id") in self.server.tutor.sessions
            normal = data.get("fault") in ("drop", "delay", "malformed") and data.get("operation") in ("settings", "generate")
            if not (stale or normal):
                return super().send_json(400, {"error": "invalid_fixture_fault"})
            if stale:
                data["snapshot"] = self.server.tutor.view(self.server.tutor.get(data["session_id"]))
            self.server.fault = data
            return super().send_json(200, {"armed": True})
        return super().run_request(method)

    def send_json(self, status, data):
        operation = self.path.rsplit("/", 1)[-1]
        received = getattr(self, "received", {})
        if "request_id" in received:
            self.server.requests.append({"operation": operation, "request_id": received["request_id"],
                                         "expected_revision": received.get("expected_revision"), "status": status,
                                         "idempotent_replay": data.get("idempotent_replay", False)})
        self.server.save()
        fault = self.server.fault
        matches = fault and (operation == fault["operation"] or fault["operation"] == "view" and self.command == "GET" and self.path == "/tutor/sessions/" + fault.get("session_id", ""))
        if status == 200 and matches:
            self.server.fault = None
            if fault["fault"] == "delay":
                time.sleep(2)
            elif fault["fault"] == "drop":
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
                return
            elif fault["fault"] == "malformed":
                return super().send_json(200, {"intentionally_invalid_fixture": True})
            elif fault["fault"] == "stale":
                return super().send_json(200, fault["snapshot"])
        return super().send_json(status, data)


class AcceptanceServer(Server):
    def __init__(self, live, output):
        self.live, self.output, self.fault, self.requests = live, output, None, []
        model = LimitedLiveModel() if live else AcceptanceFixture()
        super().__init__(("127.0.0.1", 8767), Experiment(model, output / "logs"), TutorSessions(model, output / "logs"))
        self.RequestHandlerClass = AcceptanceHandler

    def report(self):
        model = self.tutor.model
        return {"mode": model.mode, "model": model.model, "attempts": getattr(model, "attempts", 0),
                "fixture_calls": getattr(model, "calls", []), "records": getattr(model, "records", []), "requests": list(self.requests)}

    def save(self):
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "server.json").write_text(json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[2] / "StudyData/macos/tutor-acceptance" / ("live" if args.live else "fixture")
    server = AcceptanceServer(args.live, output)
    print(json.dumps({"listening": "127.0.0.1:8767", "mode": server.tutor.model.mode, "attempt_limit": 18 if args.live else 0}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.save()
        server.server_close()
