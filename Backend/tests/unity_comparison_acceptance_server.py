"""Stage-two localhost acceptance. --live permits at most 14 provider attempts.

No automatic retries, credential fallback, study participants or production fault routes.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Experiment
from model import DeepSeekModel, ModelError
from server import Server, Handler
from tutor_session import TutorSessions
from unity_comparison_fixture_server import ComparisonFixture


class LimitedComparisonModel(DeepSeekModel):
    def __init__(self):
        super().__init__(os.environ.get("DEEPSEEK_MODEL", ""), timeout=60, max_attempts=1)
        self.fallback_key = ""
        self.attempts, self.records = 0, []
        self.budget_lock = threading.RLock()

    def _call(self, role, system, context):
        with self.budget_lock:
            if self.attempts >= 14:
                raise ModelError("Comparison acceptance provider budget exhausted.")
            self.attempts += 1
        try:
            value, records = super()._call(role, system, context)
        except ModelError as exc:
            with self.budget_lock: self.records.extend(exc.records)
            raise
        with self.budget_lock: self.records.extend(records)
        return value, records


class AcceptanceHandler(Handler):
    def parse_body(self):
        self.received = super().parse_body()
        return self.received

    def run_request(self, method):
        if method == "GET" and self.path == "/engineering/status":
            return super().send_json(200, self.server.report())
        if method == "POST" and self.path == "/engineering/arm" and not self.server.live:
            data = self.parse_body()
            fault, operation = data.get("fault"), data.get("operation")
            allowed = (fault in ("malformed", "delay") and operation == "settings") or (fault == "stale" and operation == "view")
            if not allowed: return super().send_json(400, {"error": "invalid_fixture_fault"})
            if fault == "stale":
                with self.server.report_lock:
                    data["snapshot"] = deepcopy(self.server.snapshots.get((data.get("task_id"), data.get("revision"))))
                if not data["snapshot"]: return super().send_json(400, {"error": "snapshot_not_found"})
            with self.server.report_lock: self.server.fault = data
            return super().send_json(200, {"armed": True})
        return super().run_request(method)

    def send_json(self, status, data):
        operation = self.path.rsplit("/", 1)[-1]
        received = getattr(self, "received", {})
        with self.server.report_lock:
            if data.get("task_id") and "revision" in data:
                self.server.snapshots[(data["task_id"], data["revision"])] = deepcopy(data)
            if received.get("request_id"):
                self.server.requests.append({"operation": operation, "request_id": received["request_id"], "status": status,
                                             "idempotent_replay": data.get("idempotent_replay", False)})
            fault = self.server.fault
            matches = fault and (self.command == "POST" and operation == fault["operation"] or self.command == "GET" and fault["operation"] == "view" and self.path == "/tutor/comparisons/" + fault.get("task_id", ""))
            if 200 <= status < 300 and matches:
                self.server.fault = None
                self.server.faults_fired.append({"fault": fault["fault"], "operation": fault["operation"]})
            else: fault = None
            self.server.save()
        if fault:
            if fault["fault"] == "malformed": return super().send_json(status, {"intentionally_invalid_fixture": True})
            if fault["fault"] == "stale": return super().send_json(status, fault["snapshot"])
            if fault["fault"] == "delay": time.sleep(2)
        return super().send_json(status, data)


class AcceptanceServer(Server):
    def __init__(self, live):
        self.live = live
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.output = Path(__file__).resolve().parents[2] / "StudyData/macos/tutor-comparison-acceptance" / ("live" if live else "fixture") / stamp
        self.report_lock = threading.RLock()
        self.fault, self.requests, self.snapshots, self.faults_fired = None, [], {}, []
        model = LimitedComparisonModel() if live else ComparisonFixture()
        super().__init__(("127.0.0.1", 8769), Experiment(model, self.output / "logs"), TutorSessions(model, self.output / "logs"))
        self.RequestHandlerClass = AcceptanceHandler

    def report(self):
        with self.report_lock:
            model = self.tutor.model
            if self.live:
                with model.budget_lock: attempts, records = model.attempts, deepcopy(model.records)
            else: attempts, records = 0, []
            return {"output": str(self.output), "mode": model.mode, "model": model.model, "attempt_limit": 14 if self.live else 0,
                    "provider_attempts": attempts, "records": records, "requests": deepcopy(self.requests), "faults_fired": deepcopy(self.faults_fired)}

    def save(self):
        with self.report_lock:
            self.output.mkdir(parents=True, exist_ok=True)
            (self.output / "server.json").write_text(json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    server = AcceptanceServer(args.live)
    print(json.dumps({"listening": "127.0.0.1:8769", "mode": server.tutor.model.mode, "attempt_limit": 14 if args.live else 0, "output": str(server.output)}), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.save(); server.server_close()
