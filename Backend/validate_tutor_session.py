#!/usr/bin/env python3
"""Bounded live controller checks (8 provider attempts max); no study collection."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from core import APIError
from model import DeepSeekModel, ModelError
from tutor_session import TutorSessions
from tutor_state import DEFAULT_SETTINGS


class BudgetModel(DeepSeekModel):
    def __init__(self):
        super().__init__(os.environ.get("DEEPSEEK_MODEL", ""), timeout=30, max_attempts=1)
        self.fallback_key = ""
        self.attempts = 0

    def _call(self, role, system, context):
        if self.attempts >= 8:
            raise ModelError("Engineering provider budget exhausted.")
        self.attempts += 1
        return super()._call(role, system, context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "StudyData/macos/tutor-session-validation.json")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to enable up to eight paid-provider calls.")
    model = BudgetModel()
    app = TutorSessions(model, args.output.parent / "tutor-session-check")
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "scope": "Live controller engineering only; no generated tutor answers, UI, audio, headset or participant evidence.",
              "requested_model": model.model, "provider_attempt_budget": 8, "cases": []}

    def mutate(v, operation, **kwargs):
        return app.mutate(v["session_id"], operation, {"request_id": uuid.uuid4().hex, "expected_revision": v["revision"], **kwargs})

    for label in ("E_execute_undo", "A_confirm_one_turn", "N_native_gate", "S_clear_replay", "S_ambiguity_free_text"):
        condition = label[0]
        settings = {**DEFAULT_SETTINGS, "reply_length": "detailed"} if label == "S_ambiguity_free_text" else dict(DEFAULT_SETTINGS)
        v = app.create({"condition": condition, "settings": settings})
        case = {"label": label, "session_id": v["session_id"], "checks": {}}
        try:
            query = "Give me only the key points from now on."
            if condition == "A":
                query = "For this answer only, give just the key point: what is active recall?"
            elif label == "S_ambiguity_free_text":
                query = "Shorter answers please. I am not sure whether I want just the key point or the key point with a short reason."
            data = {"request_id": uuid.uuid4().hex, "expected_revision": v["revision"], "query": query}
            v = app.mutate(v["session_id"], "request", data)
            case["initial_view"] = v
            if condition == "E":
                case["checks"]["executes_brief"] = v["decision"] == "ACT" and v["settings"]["reply_length"] == "brief"
                v = mutate(v, "undo", field="reply_length")
                case["checks"]["undo_restores_settings"] = v["settings"] == settings
            elif condition == "A":
                case["checks"]["asks_without_edit"] = v["decision"] == "ASK" and v["settings"] == settings
                v = mutate(v, "request", query="Yes, please.", question_id=v["question"]["question_id"])
                case["checks"]["spoken_confirmation"] = v["decision"] == "ACT" and v["question"] is None
                case["checks"]["one_turn_only"] = v["settings"] == settings and len(v["generation_jobs"]) == 1 and v["generation_jobs"][0]["settings"]["reply_length"] == "brief"
            elif condition == "N":
                decision = v["decision"]
                case["checks"]["allowed_native_decision"] = decision in ("ACT", "ASK", "UNRESOLVED")
                if decision == "ASK":
                    case["checks"]["ask_preserves_settings"] = v["settings"] == settings
                    option = next(o["id"] for o in v["question"]["options"] if o["id"] not in ("other", "cancel"))
                    v = mutate(v, "answer", question_id=v["question"]["question_id"], option_id=option)
                case["checks"]["valid_result"] = v["settings"] == (settings if decision == "UNRESOLVED" else {**settings, "reply_length": "brief"})
            elif label == "S_clear_replay":
                case["checks"]["clear_act"] = v["decision"] == "ACT" and v["settings"]["reply_length"] == "brief"
                before_calls = model.attempts
                v = app.mutate(v["session_id"], "request", data)
                case["checks"]["replay_without_provider_call"] = v.get("idempotent_replay") is True and model.attempts == before_calls
            else:
                case["checks"]["divergence_asks"] = v["decision"] == "ASK" and v.get("reason") == "R3_MATERIAL_DIVERGENCE" and v["settings"] == settings
                v = mutate(v, "answer", question_id=v["question"]["question_id"], option_id="other",
                           free_text="Keep the key point and a short reason, without an example.")
                case["checks"]["free_text_resolved_without_new_gate"] = v["decision"] == "ACT" and v["settings"] == {**settings, "reply_length": "balanced"} and v["question"] is None
            case["final_view"] = v
        except (APIError, KeyError, TypeError) as exc:
            case["error"] = str(exc)
            case["checks"]["completed"] = False
        events = [json.loads(line) for line in (app.log_dir / (case["session_id"] + ".jsonl")).read_text().splitlines()]
        case["model_calls"] = [e["record"] for e in events if e["event"] == "model_call"]
        case["checks"]["one_gate_per_initial_request"] = sum(e["event"] == "gate_decision" for e in events) == 1
        if condition == "N":
            case["checks"]["native_model_called"] = any(c["role"] == "tutor_native_gate" for c in case["model_calls"])
        case["passed"] = all(case["checks"].values())
        report["cases"].append(case)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"case": label, "passed": case["passed"], "checks": case["checks"], "provider_attempts": model.attempts}), flush=True)
        if "error" in case:
            break
    report["provider_attempts"] = model.attempts
    report["all_passed"] = len(report["cases"]) == 5 and all(c["passed"] for c in report["cases"])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "provider_attempts": model.attempts, "all_passed": report["all_passed"]}))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
