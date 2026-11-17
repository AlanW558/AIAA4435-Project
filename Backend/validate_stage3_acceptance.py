#!/usr/bin/env python3
"""Stage-three headless engineering acceptance. --live: <=18 attempts, no retries.

Not participant data, actual STT/audio/headset validation, or a final study script.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import sys
import threading
import time
import uuid

from core import APIError
from model import DeepSeekModel, ModelError
from tutor_comparison_service import TutorComparisons
from tutor_dialogue_log import export_rows
from tutor_feedback import RATINGS
from tutor_state import DEFAULT_SETTINGS
from export_tutor_dialogue import export_file

INITIAL = "From now on, reduce your current speech speed by 10%, use Voice A, use friendly wording, and give only the key answer without optional explanations or examples. Keep your appearance unchanged. What is active recall?"
DEFAULT_RATE = "Set your speech speed to 90% of the model's default speed. Keep all other settings unchanged."
GREEN = "Change your jacket colour to green and wear the sportswear outfit. Keep your glasses, scale, identity and all dialogue settings unchanged."
PURPLE = "Change only your jacket colour to purple."
RESTORE = "Restore the jacket colour you used immediately before purple. Keep your current outfit and every other setting."
TEMPORARY = "For this answer only, use encouraging wording and include a key answer, a reason and a relevant example. Keep the other settings. How can I start practising active recall today?"
FOLLOWUP = "How could I check whether I remembered something correctly?"
RESTORE_RATE = "Restore only the speech speed that we started this task with, before any of my changes. Keep Voice A and all other current settings."
INVALID = "Set speech speed to 2 times the model's default speed and switch to Voice B. Both changes are required together; do not apply only one."
AMBIGUOUS = "Make the tutor feel calmer. I have not decided whether I mean slower speech or more professional, neutral wording. Those are alternatives, not a request for both. Keep Voice A, reply length and appearance unchanged."


def load_environment(path):
    """Read only relevant dotenv assignments; never execute shell or print values."""
    allowed = {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"}
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "): line = line[7:]
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed or key in os.environ: continue
        pieces = shlex.split(value, comments=True)
        if len(pieces) == 1: os.environ[key] = pieces[0]


class BoundedModel(DeepSeekModel):
    def __init__(self, limit=18):
        super().__init__(os.environ.get("DEEPSEEK_MODEL", ""), timeout=30, max_attempts=1)
        self.fallback_key = ""
        self.limit, self.attempts, self.records = limit, 0, []
        self.budget_lock = threading.Lock()

    def _call(self, role, system, context):
        with self.budget_lock:
            if self.attempts >= self.limit: raise ModelError("Stage-three attempt budget exhausted")
            self.attempts += 1
            attempt = self.attempts
        print(json.dumps({"provider_attempt": attempt, "limit": self.limit, "role": role}), flush=True)
        try:
            result, records = super()._call(role, system, context)
        except ModelError as exc:
            with self.budget_lock: self.records.extend(deepcopy(exc.records))
            raise
        with self.budget_lock: self.records.extend(deepcopy(records))
        return result, records


def fixture_model():
    sys.path.insert(0, str(Path(__file__).parent / "tests"))
    from test_tutor_generation import GenerationFixture, parts
    from test_tutor_multidomain import proposal
    from test_tutor_session import chat
    class SequenceFixture(GenerationFixture):
        model = "stage3-sequence-fixture"
        def interpret_tutor(self, context):
            query = context["query"]
            cases = {
                INITIAL: proposal({"speech_rate": {"basis": "current", "operation": "multiply", "value": .9}, "voice": "voice_a", "tone": "friendly", "reply_length": "brief"}),
                DEFAULT_RATE: proposal({"speech_rate": {"basis": "default", "operation": "multiply", "value": .9}}),
                GREEN: proposal({"jacket_color": "green", "outfit": "sport"}),
                PURPLE: proposal({"jacket_color": "purple"}),
                RESTORE: proposal({"jacket_color": "green"}),
                TEMPORARY: proposal({"tone": "encouraging", "reply_length": "detailed"}, scope="turn"),
                FOLLOWUP: chat(FOLLOWUP),
                RESTORE_RATE: proposal({"speech_rate": 1.2}),
                INVALID: proposal({"speech_rate": 2.0, "voice": "voice_b"}),
                AMBIGUOUS: proposal({"speech_rate": 1.1}, {"tone": "professional"}, required=[], preserved=["voice", "reply_length", "avatar_id", "outfit", "jacket_color", "accessory", "scale"]),
            }
            raw = deepcopy(cases[query])
            if query in (INITIAL, TEMPORARY): raw.update(kind="mixed", conversation_query="What is active recall?" if query == INITIAL else "How can I start practising active recall today?")
            return self._return("interpret", context, raw)
        def generate_tutor(self, context):
            tone = context["tone_style"]["mode"]
            return self._return("generate", context, parts(tone + " key answer.", tone + " supporting reason.", tone + " example."))
    return SequenceFixture()


class Acceptance:
    def __init__(self, model, folder):
        self.model, self.folder = model, Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.app = TutorComparisons(model, self.folder / "logs")
        self.task_id, self.first, self.baseline = None, None, None
        self.report = {"scope": "Headless engineering only. No STT, TTS, Unity presentation or participant evidence. Feedback is synthetic; old Q1-Q7 contract only, not the revised study questionnaire.",
                       "mode": model.mode, "model": model.model, "attempt_limit": getattr(model, "limit", 0), "checks": [], "tasks": [], "snapshots": []}

    def save(self):
        self.report["provider_attempts"] = getattr(self.model, "attempts", 0)
        (self.folder / "report.json").write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")

    def check(self, okay, label):
        self.report["checks"].append({"name": label, "passed": bool(okay)})
        self.save()
        if not okay: raise AssertionError(label)

    def view(self): return self.app.view(self.app.get(self.task_id))

    def command(self, op, c=None, **payload):
        v = self.view()
        key = "expected_revision" if c is None else "expected_branch_revision"
        return self.app.mutate(self.task_id, op, {"request_id": uuid.uuid4().hex, key: v["revision"] if c is None else v["branches"][c]["branch_revision"], **payload}, c)

    def settle(self):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            v = self.view()
            if v["shared_preparation"]["status"] == "failed" or any(b["status"] == "failed" for b in v["branches"].values()):
                raise AssertionError("Branch/shared failure; no automatic retry")
            if all(b["status"] not in ("idle", "processing") for b in v["branches"].values()): return v
            time.sleep(.02)
        raise TimeoutError("Acceptance branch wait exceeded")

    def snapshot(self, label):
        path = label + ".json"
        (self.folder / path).write_text(json.dumps(self.view(), ensure_ascii=False, indent=2) + "\n")
        self.report["snapshots"].append(path)
        self.save()
        print(json.dumps({"step": label, "checks_passed": sum(c["passed"] for c in self.report["checks"]), "provider_attempts": getattr(self.model, "attempts", 0)}), flush=True)

    def create(self, code, settings):
        v = self.app.create({"request_id": uuid.uuid4().hex, "task_code": code, "domain": "speech_rate", "scenario": "C1", "participant_id": "STAGE3FIXTURE", "settings": settings})
        self.task_id = v["task_id"]
        self.report["tasks"].append(self.task_id)
        self.baseline = deepcopy(v["baseline"])
        return v

    def respond(self, c, alternative=False):
        q = self.view()["branches"][c]["question"]
        ids = [o["id"] for o in q["options"] if o["id"] not in ("other", "cancel")]
        self.command("answer", c, question_id=q["question_id"], response={"option_id": ids[-1] if alternative else ids[0]})
        return self.settle()

    def reveal(self, divergent=False):
        v = self.settle()
        self.check(not v["results_visible"], "Results remain hidden while A awaits clarification")
        for c in "EANS":
            if self.view()["branches"][c]["status"] == "awaiting_clarification":
                self.respond(c, alternative=divergent and c == "S")
                current = self.view()
                if any(b["status"] == "awaiting_clarification" for b in current["branches"].values()):
                    self.check(not current["results_visible"] and all(b["result"] is None for b in current["branches"].values()), "No early result after partial clarification")
        v = self.view()
        self.check(v["results_visible"], "All actual clarifications resolved before reveal")
        self.first = deepcopy(v["first_reveal"])
        return v

    def settings(self, c="E"): return self.view()["branches"][c]["result"]["state"]["settings"]

    def request(self, query):
        self.command("request", "E", query=query)
        v = self.settle()
        self.check(v["branches"]["E"]["status"] == "ready", "E follow-up settled")
        self.check(v["first_reveal"] == self.first, "First snapshot immutable through continuous interaction")
        self.check(all(v["branches"][c]["result"]["state"] == self.first["branches"][c]["state"] for c in "ANS"), "Repair preserves other strategies")
        return v

    def feedback(self, c):
        v = self.view()
        self.command("feedback", c, expected_feedback_revision=v["feedback"][c]["feedback_revision"],
                     answers={"completion": "unable_to_judge", "ratings": {q: "unable_to_judge" for q in RATINGS}, "comment": "Synthetic engineering check; not participant data.", "comment_confirmed": True})

    def sequence(self):
        self.create("STAGE3-CONTINUOUS", {"speech_rate": 1.2})
        self.command("start", query=INITIAL)
        self.settle()
        self.check(self.view()["branches"]["A"]["status"] == "awaiting_clarification", "Always ask holds initial combined edit")
        self.command("pause")
        self.check(self.view()["lifecycle"] == "paused" and not self.view()["results_visible"], "Pause retains hidden baseline")
        self.command("resume")
        self.snapshot("01-hidden")
        v = self.reveal()
        expected = {**DEFAULT_SETTINGS, "speech_rate": 1.08, "voice": "voice_a", "tone": "friendly", "reply_length": "brief"}
        self.check(all(self.settings(c) == expected for c in "EANS"), "All four initial properties apply together; appearance preserved")
        self.check(all(len(v["branches"][c]["result"]["state"]["conversation"]) == 1 for c in "EANS"), "Each branch contains its initial generated answer")
        self.snapshot("02-initial-reveal")
        for c in "EANS": self.feedback(c)
        self.request(DEFAULT_RATE)
        expected["speech_rate"] = .9
        self.check(self.settings() == expected, "Default rate basis differs from current-rate reduction")
        self.check(not self.view()["feedback"]["E"]["current"] and all(self.view()["feedback"][c]["current"] for c in "ANS"), "Repair invalidates only its branch's prior feedback")
        self.request(GREEN)
        expected.update(jacket_color="green", outfit="sport")
        self.check(self.settings() == expected, "Appearance adjustment preserves all dialogue settings")
        self.request(PURPLE)
        expected["jacket_color"] = "purple"
        self.check(self.settings() == expected, "Second colour recorded without unrelated edits")
        self.request(RESTORE)
        expected["jacket_color"] = "green"
        self.check(self.settings() == expected, "Natural-language history restores actual pre-purple colour")
        self.snapshot("03-appearance-history")
        self.request(TEMPORARY)
        self.check(self.settings() == expected, "One-answer request leaves persistent controls untouched")
        exchange = self.view()["branches"]["E"]["result"]["state"]["conversation"][-1]
        self.check(exchange["settings"] == {**expected, "tone": "encouraging", "reply_length": "detailed"}, "One-answer response gets exact combined snapshot")
        self.request(FOLLOWUP)
        self.check(self.view()["branches"]["E"]["result"]["state"]["conversation"][-1]["settings"] == expected, "Following answer returns to persistent settings")
        self.snapshot("04-one-answer-and-followup")
        self.request(RESTORE_RATE)
        expected["speech_rate"] = 1.2
        self.check(self.settings() == expected, "Task-start rate restored without restoring unrelated fields")
        self.request(INVALID)
        self.check(self.settings() == expected and self.view()["branches"]["E"]["result"]["outcome"] == "unresolved", "Unsupported combined request applies neither rate nor Voice")
        self.command("undo", "E", field="speech_rate"); self.settle()
        expected["speech_rate"] = .9
        self.check(self.settings() == expected, "Scoped undo preserves later appearance and dialogue state")
        self.feedback("E")
        self.check(self.view()["can_submit"], "Current synthetic feedback permits submission")
        self.command("submit")
        self.check(self.view()["lifecycle"] == "submitted" and self.view()["first_reveal"] == self.first, "Submission binds final feedback and immutable first reveal")
        self.snapshot("05-submitted")
        previous = self.task_id
        self.command("next", next_task={"task_code": "STAGE3-ALTERNATIVES", "domain": "tone", "scenario": "C3", "settings": {"speech_rate": 1.2, "tone": "friendly", "voice": "voice_a"}})
        self.task_id = self.view()["next_task_id"]
        self.report["tasks"].append(self.task_id)
        self.baseline = deepcopy(self.view()["baseline"])
        self.check(self.view()["previous_task_id"] == previous and not self.baseline["changes"] and not self.baseline["conversation"], "Next task has independent baseline and history")
        self.command("start", query=AMBIGUOUS); v = self.settle()
        self.check(v["branches"]["S"]["status"] == "awaiting_clarification", "Selective asks about materially different interpretations")
        self.snapshot("06-alternatives-hidden")
        v = self.reveal(divergent=True)
        self.check(self.settings("A") != self.settings("S"), "Independent clarification selections yield independent alternatives")
        for c in "EANS":
            self.check(all(self.settings(c)[f] == self.baseline["settings"][f] for f in ("voice", "reply_length", "avatar_id", "outfit", "jacket_color", "accessory", "scale")), "Alternatives preserve explicit constraints in " + c)
        self.command("close")
        self.check(self.view()["lifecycle"] == "aborted" and self.view()["submission_id"] is None, "Exit without ratings is not fabricated submission")
        self.snapshot("07-alternatives-aborted")

    def audit(self):
        canonical = []
        for tid in self.report["tasks"]:
            path = self.app.log_dir / (tid + ".jsonl")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            by = lambda e: [r for r in rows if r["event"] == e]
            start, finish = by("provider_started"), by("provider_finished")
            canonical.extend(r for e in finish for r in e["model_calls"])
            self.check(Counter(r["call_id"] for r in start) == Counter(r["call_id"] for r in finish), "Provider start/finish pairing " + tid)
            prepared, gates, reveals = by("shared_prepared"), by("branch_gate_plan"), by("first_reveal")
            self.check(len(prepared) == 1 and len(gates) == 4 and {g["shared_id"] for g in gates} == {prepared[0]["prepared"]["shared_id"]}, "Four gates use exactly one shared interpretation " + tid)
            self.check(len(reveals) == 1, "Exactly one first reveal " + tid)
            prior = rows[:rows.index(reveals[0])]
            latest = {c: next(r for r in reversed(prior) if r["event"] == "branch_checkpoint" and r["condition"] == c) for c in "EANS"}
            self.check(all(r["result"]["question"] is None and all(j["status"] == "completed" for j in r["result"]["generation_jobs"]) for r in latest.values()), "Reveal follows resolved questions and completed generation " + tid)
            evidence = list(export_rows(enumerate(rows, 1)))
            answers = [r for r in evidence if r["kind"] == "answer"]
            checkpoints = [r for r in evidence if r["kind"] == "checkpoint"]
            self.check(all(any(c["scope"] == a["scope"] and any(j["job_id"] == a["job_id"] and j["text_sha256"] == a["text_sha256"] for j in c["completed_answers"]) for c in checkpoints) for a in answers), "Every successful answer links to exact committed text " + tid)
            self.check(sum(r["kind"] == "request" and r["scope"] == "shared" for r in evidence) == 1, "Shared transcript counted once " + tid)
            self.check(not any(r["kind"] == "panel_presented" for r in evidence), "Headless validation does not fabricate Unity presentation " + tid)
            for submission in by("task_submitted"):
                data = submission["submission"]
                self.check(all(data["feedback"][c]["branch_revision"] == data["final_results"][c]["branch_revision"] for c in "EANS"), "Submitted feedback matches evaluated branch versions")
            export_file(path, self.folder / (tid + "-dialogue.jsonl"))
        if self.model.mode == "live":
            self.check(len(canonical) == self.model.attempts <= self.model.limit, "Unique provider accounting within hard budget")
            self.check(all(r["status"] == "ok" for r in canonical), "All provider attempts returned valid JSON")
        self.report["usage"] = {k: sum(r.get("usage", {}).get(k, 0) for r in canonical) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        self.report["response_models"] = sorted({r["response_model"] for r in canonical if r.get("response_model")})
        self.report["provider_records"] = canonical

    def run(self):
        try:
            self.sequence()
            self.audit()
            self.report["passed"] = True
        except (AssertionError, APIError, ModelError, TimeoutError, KeyError, IndexError) as exc:
            self.report["passed"] = False
            self.report["error"] = str(exc)
            if self.task_id: self.snapshot("failure-state")
        finally:
            self.app.shutdown()
            if self.model.mode == "live":
                self.report["provider_records"] = deepcopy(self.model.records)
                self.report["usage"] = {k: sum(r.get("usage", {}).get(k, 0) for r in self.model.records) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            self.save()
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.live: load_environment(root / ".env")
    model = BoundedModel() if args.live else fixture_model()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = root / "StudyData/macos/stage3-acceptance" / ("live" if args.live else "fixture") / stamp
    report = Acceptance(model, folder).run()
    print(json.dumps({"passed": report["passed"], "checks": len(report["checks"]), "provider_attempts": report["provider_attempts"], "error": report.get("error"), "folder": str(folder)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
