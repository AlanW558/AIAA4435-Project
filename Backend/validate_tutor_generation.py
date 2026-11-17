#!/usr/bin/env python3
"""Live HTTP question-to-answer engineering check, at most 14 provider attempts.

Stores actual answers for human content review. Automated checks cover state,
history, routing and replay, NOT language quality or participant task success.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import urllib.error
import urllib.request
import uuid

from core import Experiment
from model import DeepSeekModel, ModelError
from server import Server
from tutor_session import TutorSessions


class BudgetModel(DeepSeekModel):
    def __init__(self):
        super().__init__(os.environ.get("DEEPSEEK_MODEL", ""), timeout=60, max_attempts=1)
        self.fallback_key = ""
        self.attempts = 0
        self.last_failure = None

    def _call(self, role, system, context):
        if self.attempts >= 14:
            raise ModelError("Engineering provider budget exhausted.")
        self.attempts += 1
        self.last_failure = None
        try:
            return super()._call(role, system, context)
        except ModelError as exc:
            self.last_failure = exc.records[-1] if exc.records else None
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--retry-transient", action="store_true", help="Allow one explicit transient-failure retry across the entire check, within the same 14-attempt cap.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "StudyData/macos/tutor-generation-validation.json")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to enable at most fourteen provider attempts.")
    model = BudgetModel()
    log_dir = args.output.parent / "tutor-generation-check"
    tutor = TutorSessions(model, log_dir)
    server = Server(("127.0.0.1", 0), Experiment(model, log_dir), tutor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "scope": "Real-model localhost HTTP engineering; no Unity, audio, headset, participants or automatic content scoring.",
              "requested_model": model.model, "provider_attempt_budget": 14, "cases": [],
              "provider_timeout_seconds": model.timeout, "session_ids": [],
              "transient_retries": [],
              "content_review": "Pending inspection of actual answers; automated pass only covers state, history, routing and replay."}

    def save():
        report["provider_attempts"] = model.attempts
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    def post(path, data):
        req = urllib.request.Request(base + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            body = json.load(exc)
            failure = model.last_failure or {}
            transient = failure.get("error") == "provider_connection_error" or (
                failure.get("error") == "provider_http_error" and failure.get("http_status") in (408, 429, 500, 502, 503, 504))
            if args.retry_transient and not report["transient_retries"] and model.attempts < 14 and exc.code == 502 and body.get("error") == "model_error" and transient and "request_id" in data:
                retry_id = uuid.uuid4().hex
                report["transient_retries"].append({"failed_request_id": data["request_id"], "retry_request_id": retry_id,
                                                    "provider_error": failure.get("error"), "provider_http_status": failure.get("http_status")})
                save()
                return post(path, {**data, "request_id": retry_id})
            raise RuntimeError(f"HTTP {exc.code}: {body.get('error', 'unknown')}") from None

    def mutate(view, operation, **kwargs):
        return post("/tutor/sessions/" + view["session_id"] + "/" + operation,
                    {"request_id": uuid.uuid4().hex, "expected_revision": view["revision"], **kwargs})

    def ask_and_generate(view, label, query, expected_length, expected_persistent, prior_exchanges):
        view = mutate(view, "request", query=query)
        if view["question"] is not None:
            raise RuntimeError("Unexpected clarification in this clear engineering case; inspect its log.")
        job = next((j for j in view["generation_jobs"] if j["status"] == "queued"), None)
        if job is None:
            raise RuntimeError("The request did not queue a learning question.")
        view = mutate(view, "generate", job_id=job["job_id"])
        events = [json.loads(line) for line in (tutor.log_dir / (view["session_id"] + ".jsonl")).read_text().splitlines()]
        generated = next(e for e in reversed(events) if e["event"] == "answer_generated" and e["job_id"] == job["job_id"])
        checks = {"actual_answer": view["decision"] == "ANSWER" and bool(view["response"]["text"].strip()),
                  "used_structure": view["response"]["settings"]["reply_length"] == expected_length,
                  "persistent_setting": view["settings"]["reply_length"] == expected_persistent,
                  "history_in_context": len(generated["context"]["conversation"]) == prior_exchanges * 2,
                  "one_exchange_added": len(view["conversation"]) == prior_exchanges + 1,
                  "recorded_effective_settings": view["conversation"][-1]["settings"]["reply_length"] == expected_length}
        before_calls = model.attempts
        replay = mutate(view, "generate", job_id=job["job_id"])
        checks["completed_job_reused"] = replay["generation_replay"] and model.attempts == before_calls and len(replay["conversation"]) == len(view["conversation"])
        case = {"label": label, "session_id": view["session_id"], "query": query,
                "answer": view["response"]["text"], "generation_context": generated["context"],
                "used_reply_length": view["response"]["settings"]["reply_length"],
                "persistent_reply_length": view["settings"]["reply_length"], "checks": checks,
                "passed_transport_and_state": all(checks.values())}
        report["cases"].append(case)
        save()
        print(json.dumps({"case": label, "passed_transport_and_state": case["passed_transport_and_state"], "provider_attempts": model.attempts}), flush=True)
        if not all(checks.values()):
            raise RuntimeError("A state or history check failed; see local report.")
        return replay

    try:
        question = "What is an effective way to check whether I understand a concept?"
        brief_view = None
        for length in ("brief", "balanced", "detailed"):
            view = post("/tutor/sessions", {"condition": "S"})
            report["session_ids"].append(view["session_id"])
            if length == "brief":
                view = mutate(view, "request", query="Give me only the key points from now on.")
                if view["decision"] != "ACT" or view["settings"]["reply_length"] != "brief":
                    raise RuntimeError("Clear persistent length request did not apply as expected.")
            elif length == "detailed":
                view = mutate(view, "settings", patch={"reply_length": "detailed"})
            view = ask_and_generate(view, length, question, length, length, 0)
            if length == "brief":
                brief_view = view
        brief_view = ask_and_generate(brief_view, "brief_followup", "Why would the method you just suggested help me find gaps?", "brief", "brief", 1)
        brief_view = mutate(brief_view, "settings", patch={"reply_length": "detailed"})
        brief_view = ask_and_generate(brief_view, "one_turn_brief", "For this answer only, give just the key point: how should I begin a revision session?", "brief", "detailed", 2)
        ask_and_generate(brief_view, "after_one_turn", "Why would that be a useful first step?", "detailed", "detailed", 3)
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        report["error"] = str(exc)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        report["all_transport_and_state_passed"] = len(report["cases"]) == 6 and all(c["passed_transport_and_state"] for c in report["cases"]) and "error" not in report
        records = []
        for sid in report["session_ids"]:
            for line in (tutor.log_dir / (sid + ".jsonl")).read_text().splitlines():
                event = json.loads(line)
                if event["event"] == "model_call":
                    records.append(event["record"])
        report["model_calls"] = records
        save()
    print(json.dumps({"output": str(args.output), "provider_attempts": model.attempts,
                      "all_transport_and_state_passed": report["all_transport_and_state_passed"]}))
    return 0 if report["all_transport_and_state_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
