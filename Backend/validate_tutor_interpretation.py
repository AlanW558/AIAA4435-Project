#!/usr/bin/env python3
"""Eight bounded live engineering checks; no participants, changes, or tutor replies.

Credentials/model come from the existing private environment. No fallback account
or automatic retries in this check. Output is a local, ignored engineering report.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from model import DeepSeekModel, ModelError
from tutor_interpretation import INTERPRETER_VERSION, TutorInterpreter
from tutor_state import TutorState


def cases():
    history = TutorState()
    history.commit({"reply_length": "brief"}, expected_revision=0, source="request", query="Key points only.")
    history.commit({"reply_length": "detailed", "tone": "friendly"}, expected_revision=1,
                   source="request", query="Include full reasoning and an example, and use friendly wording.")
    detailed = TutorState()
    detailed.commit({"reply_length": "detailed"}, expected_revision=0, source="direct_control")
    question = {"original_query": "Only give the key points from now on.", "text": "Use Brief replies?",
                "options": [{"id": "c1", "label": "Brief: key points only"},
                            {"id": "other", "label": "Something else"}, {"id": "cancel", "label": "Cancel"}]}
    return [
        ("ordinary_question", TutorState(), "What does tone mean in academic writing?", {},
         {"kind": "chat"}),
        ("clear_persistent", TutorState(), "Give me only the key points from now on.", {},
         {"kind": "tailoring", "scope": "session", "targets": ["brief"]}),
        ("mixed_one_turn", TutorState(), "For this answer only, give just the key point: what is active recall?", {},
         {"kind": "mixed", "scope": "turn", "targets": ["brief"]}),
        ("relative_structure", detailed, "Make the answer a little less detailed. Keep the key point and a short reason, but remove the example.", {},
         {"kind": "tailoring", "targets": ["balanced"]}),
        ("historical_restore", history, "Restore the initial key-point-plus-short-reason format, while keeping the friendly tone you now have.", {},
         {"kind": "tailoring", "targets": ["balanced"]}),
        ("two_structures", detailed, "Shorter answers please. I am not sure whether I want just the key point or the key point with a short reason.", {},
         {"kind": "tailoring", "targets": ["brief", "balanced"]}),
        ("unsupported_pitch", TutorState(), "Raise the voice pitch by two semitones and make your answers key points only.", {},
         {"kind": "tailoring", "supported": False}),
        ("answer_existing_question", TutorState(), "Yes, please.", {"pending": question},
         {"kind": "clarification", "option_id": "c1"}),
    ]


def checks(result, expected, settings):
    result = result["interpretation"]
    passed = {"kind": result["kind"] == expected["kind"]}
    if "scope" in expected:
        passed["scope"] = result["scope"] == expected["scope"]
    if "targets" in expected:
        proposal = result["proposal"] or {}
        passed["targets"] = proposal.get("supported") is True and sorted(
            c["patch"].get("reply_length", settings["reply_length"]) for c in proposal.get("candidates", [])
        ) == sorted(expected["targets"])
    if "supported" in expected:
        passed["supported"] = (result["proposal"] or {}).get("supported") is expected["supported"]
    if "option_id" in expected:
        passed["option_id"] = (result["clarification"] or {}).get("option_id") == expected["option_id"]
    if expected["kind"] == "mixed":
        passed["question_preserved"] = "active recall" in result["conversation_query"].lower()
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly enable up to eight provider calls.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "StudyData/macos/tutor-interpretation-validation.json")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to run this paid-provider engineering check.")
    model = DeepSeekModel(os.environ.get("DEEPSEEK_MODEL", ""), timeout=30, max_attempts=1)
    model.fallback_key = ""  # Strict one configured account, eight-attempt maximum.
    interpreter = TutorInterpreter(model)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "version": INTERPRETER_VERSION,
              "scope": "Engineering interpretation only; no strategy execution, tutor generation, Unity, audio or participant evidence.",
              "requested_model": model.model, "max_provider_attempts": 8, "cases": []}
    for label, state, query, kwargs, expected in cases():
        before = state.snapshot()
        item = {"label": label, "query": query, "expected": expected}
        stop = False
        try:
            result = interpreter.interpret(query, before, **kwargs)
            item.update(result=result, checks=checks(result, expected, before["settings"]))
        except ModelError as exc:
            item.update(error=str(exc), model_calls=exc.records, checks={"interpretation_returned": False})
            # Do not repeatedly spend calls after an account/network outage.
            stop = not exc.records or any(record.get("status") != "ok" for record in exc.records)
        item["checks"]["state_unchanged"] = state.snapshot() == before
        item["passed"] = all(item["checks"].values())
        report["cases"].append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"case": label, "passed": item["passed"], "checks": item["checks"]}), flush=True)
        if stop:
            break
    report["provider_attempts"] = sum(len(item.get("result", item).get("model_calls", [])) for item in report["cases"])
    report["all_passed"] = len(report["cases"]) == 8 and all(item["passed"] for item in report["cases"])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "provider_attempts": report["provider_attempts"], "all_passed": report["all_passed"]}))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
