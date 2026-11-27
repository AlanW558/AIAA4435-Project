"""Bounded, opt-in engineering acceptance against real speech and tutor APIs.

Generated WAVs are synthetic test fixtures, never participant recordings. Uses
the production Python services (including their context/visibility guards), but
does not use Unity, microphone input, production sessions, or formal study data.
No credentials, raw provider errors, or signed audio URLs enter the report.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))
from core import APIError
from model import DeepSeekModel, ModelError
from speech import SpeechConfig, SpeechError, SpeechService
from tutor_audio import TutorAudio
from tutor_comparison_service import TutorComparisons
from tutor_session import TutorSessions
from tutor_state import DEFAULT_SETTINGS
from tutor_transcription import TutorTranscription
from tutor_voice_catalog import VOICE_IDS, SAMPLE_TEXT


def uid():
    return uuid.uuid4().hex


def literals(path):
    allowed = {"QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_ASR_MODEL", "QWEN_TTS_MODEL",
               "QWEN_TIMEOUT_SECONDS", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"}
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        key, sep, value = line.partition("=")
        if key.strip() not in allowed:
            continue
        if not sep or "$" in value or "`" in value:
            raise ValueError("literal_configuration_required")
        parts = shlex.split(value, comments=True)
        if len(parts) > 1:
            raise ValueError("literal_configuration_required")
        result[key.strip()] = parts[0] if parts else ""
    return result


class BoundedModel(DeepSeekModel):
    def __init__(self, name):
        super().__init__(name, timeout=45, max_attempts=1)
        self.fallback_key = ""  # No hidden second account or automatic retries.
        self.calls, self.call_lock = [], threading.Lock()

    def _call(self, role, system, context):
        with self.call_lock:
            if len(self.calls) >= 60:
                raise ModelError("engineering_budget_reached")
            entry = {"number": len(self.calls) + 1, "role": role, "status": "running"}
            self.calls.append(entry)
        started = time.monotonic()
        try:
            result, records = super()._call(role, system, context)
            entry.update(status="ok", usage=records[-1].get("usage", {}))
            return result, records
        except ModelError as error:
            entry.update(status="failed", errors=[{k: r[k] for k in ("error", "http_status") if k in r} for r in error.records])
            raise
        finally:
            entry["seconds"] = round(time.monotonic() - started, 3)


class BoundedSpeech(SpeechService):
    def __init__(self, config):
        super().__init__(config)
        self.usage_class = "output_tts"
        self.counts = {"input_tts": 0, "asr": 0, "output_tts": 0}
        self.calls = []

    def begin(self, kind):
        cap = 10 if kind == "output_tts" else 15
        if self.counts[kind] >= cap:
            raise ValueError("engineering_speech_budget_reached")
        self.counts[kind] += 1
        entry = {"kind": kind, "number": self.counts[kind], "status": "running"}
        self.calls.append(entry)
        return entry

    def synthesize(self, text, settings, **kwargs):
        entry = self.begin(self.usage_class)
        try:
            result = super().synthesize(text, settings, **kwargs)
            entry.update(status="ok", audio_bytes=len(result["audio"]), cache_hit=result.get("cache_hit", False),
                         settings=result["settings"], model=result["model"])
            return result
        except SpeechError as error:
            entry.update(status="failed", error=error.code)
            raise

    def transcribe(self, audio, **kwargs):
        entry = self.begin("asr")
        try:
            result = super().transcribe(audio, **kwargs)
            entry.update(status="ok", model=result["model"])
            return result
        except SpeechError as error:
            entry.update(status="failed", error=error.code)
            raise


class Acceptance:
    def __init__(self, output, speech, model):
        self.output, self.speech, self.model = output, speech, model
        self.tutor = TutorSessions(model, output / "logs")
        self.comparisons = TutorComparisons(model, output / "logs", max_workers=4)
        self.tutor.audio_available = self.comparisons.audio_available = True
        self.transcription = TutorTranscription(self.tutor, self.comparisons, speech)
        self.audio = TutorAudio(self.tutor, self.comparisons, speech)
        self.checks, self.inputs = [], []
        self.sid = self.tutor.create({"participant_id": "ENGINEERING_SYNTHETIC", "condition": "S"})["session_id"]

    def save(self, name, value):
        (self.output / (name + ".json")).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    def check(self, name, passed, **details):
        self.checks.append({"name": name, "passed": bool(passed), **details})
        print(json.dumps({"check": name, "passed": bool(passed)}), flush=True)

    def session(self):
        return self.tutor.view(self.tutor.get(self.sid))

    def sm(self, op, **data):
        return self.tutor.mutate(self.sid, op, {"request_id": uid(), "expected_revision": self.session()["revision"], **data})

    def cv(self):
        return self.comparisons.view(self.comparisons.get(self.tid))

    def cm(self, op, branch=None, **data):
        view = self.cv()
        revision = {"expected_revision": view["revision"]} if branch is None else {"expected_branch_revision": view["branches"][branch]["branch_revision"]}
        return self.comparisons.mutate(self.tid, op, {"request_id": uid(), **revision, **data}, branch)

    def voice_input(self, label, text, kind="sessions", condition="S", question_id=""):
        self.speech.usage_class = "input_tts"
        generated = self.speech.synthesize(text, DEFAULT_SETTINGS)
        self.speech.usage_class = "output_tts"
        path = self.output / (label + "-synthetic-input.wav")
        path.write_bytes(generated["audio"])
        view = self.cv() if kind == "comparisons" else self.session()
        data = {"request_id": uid(), "expected_revision": view["revision"], "condition": condition,
                "question_id": question_id, "audio_base64": base64.b64encode(generated["audio"]).decode()}
        ident = self.tid if kind == "comparisons" else self.sid
        result = self.transcription.transcribe(kind, ident, data)
        count = self.speech.counts["asr"]
        replay = self.transcription.transcribe(kind, ident, data)
        self.check(label + "_asr_idempotent", replay == result and self.speech.counts["asr"] == count)
        self.inputs.append({"label": label, "fixture_type": "API_synthetic_English_not_human", "intended_text": text,
                            "recognized_text": result["text"], "audio_file": path.name,
                            "audio_sha256": hashlib.sha256(generated["audio"]).hexdigest()})
        self.save("inputs", self.inputs)
        return result["text"]

    def complete_session(self, label):
        # Any unexpected clarification is retained as an observation; choose the
        # first actual candidate via UI to settle the engineering transaction.
        view = self.session()
        if view.get("question"):
            self.check(label + "_required_clarification", True, question=view["question"])
            option = next(o for o in view["question"]["options"] if o["id"] not in ("other", "cancel"))
            self.sm("answer", question_id=view["question"]["question_id"], option_id=option["id"])
        for job in self.session()["generation_jobs"]:
            if job["status"] == "queued":
                self.sm("generate", job_id=job["job_id"])
        view = self.session()
        self.save(label + "-state", view)
        return view

    def say(self, label, text):
        query = self.voice_input(label, text)
        self.sm("request", query=query)
        return self.complete_session(label)

    def play_reply(self, label, kind="sessions", condition="S"):
        view = self.cv() if kind == "comparisons" else self.session()
        snapshot = view["branches"][condition]["result"]["state"] if kind == "comparisons" else view
        exchange = snapshot["conversation"][-1]
        data = {"request_id": uid(), "expected_revision": view["revision"], "condition": condition,
                "purpose": "reply", "exchange_id": exchange["id"]}
        audio = self.audio.synthesize(kind, self.tid if kind == "comparisons" else self.sid, data)
        (self.output / (label + "-tutor-output.wav")).write_bytes(audio)
        self.check(label + "_real_reply_tts", len(audio) > 44, settings=exchange["settings"], bytes=len(audio))

    def settle_comparison(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            view = self.cv()
            if all(b["status"] not in ("idle", "processing") for b in view["branches"].values()):
                return view
            time.sleep(.1)
        raise TimeoutError("comparison_deadline")

    def run(self):
        for voice in VOICE_IDS:
            data = self.speech.synthesize(SAMPLE_TEXT, {**DEFAULT_SETTINGS, "voice": voice})
            (self.output / (voice + "-sample.wav")).write_bytes(data["audio"])
            self.check(voice + "_provider_audio", bool(data["audio"]), returned_settings=data["settings"])

        self.sm("settings", patch={"speech_rate": 1.2})
        view = self.say("rate-default-relative", "From now on, set your speaking speed to zero point nine times the model's default speed, not your current speed. What is active recall?")
        self.check("rate_default_relative", view["settings"]["speech_rate"] == .9, actual=view["settings"]["speech_rate"])
        self.play_reply("rate-default-relative")
        self.sm("settings", patch={"speech_rate": 1.2})
        view = self.say("rate-current-relative", "From now on, set your speaking speed to zero point nine times your current speed.")
        self.check("rate_current_relative", view["settings"]["speech_rate"] == 1.08, actual=view["settings"]["speech_rate"])
        view = self.say("reply-brief", "From now on, give only the key points, without explanations or examples. How does active recall help learning?")
        self.check("reply_brief", view["settings"]["reply_length"] == "brief", actual=view["settings"]["reply_length"])
        view = self.say("tone-friendly", "From now on, use a friendly tone. How should I start practicing active recall?")
        self.check("tone_friendly", view["settings"]["tone"] == "friendly", actual=view["settings"]["tone"])
        self.play_reply("tone-friendly")
        view = self.say("voice-e", "From now on, switch to Voice E. Give me one tip for remembering English vocabulary.")
        self.check("voice_e", view["settings"]["voice"] == "voice_e", actual=view["settings"]["voice"])
        self.play_reply("voice-e")
        prior = len(view["conversation"])
        view = self.say("continuous-followup", "How could I use that tip when preparing for a vocabulary quiz tomorrow?")
        self.check("continuous_history_preserved", len(view["conversation"]) == prior + 1 and view["settings"]["tone"] == "friendly", exchange_count=len(view["conversation"]))
        previous = deepcopy(view["settings"])
        view = self.say("appearance-green", "Change your jacket color to green and keep all your other settings the same.")
        self.check("appearance_green_isolated", view["settings"] == {**previous, "jacket_color": "green"}, actual=view["settings"])
        undone = self.sm("undo", field="jacket_color")
        self.check("appearance_ui_undo", undone["settings"] == previous, actual=undone["settings"])

        created = self.comparisons.create({"request_id": uid(), "task_code": "LIVE-SYNTHETIC-REPLY", "domain": "reply_length",
                    "scenario": "C1", "participant_id": "ENGINEERING_SYNTHETIC", "feedback_version": "attribute-feedback-v2"})
        self.tid = created["task_id"]
        condition = created["selected_condition"]
        query = self.voice_input("comparison-initial", "From now on, give only the key points without explanations or examples. What is active recall?", "comparisons", condition)
        self.cm("start", query=query)
        view = self.settle_comparison()
        self.save("comparison-before-clarification", view)
        self.check("comparison_initial_barrier", not view["results_visible"] and all(b.get("result") is None for b in view["branches"].values()) and view["branches"]["A"]["status"] == "awaiting_clarification", statuses={c:b["status"] for c,b in view["branches"].items()})
        before = dict(self.speech.counts)
        try:
            self.audio.synthesize("comparisons", self.tid, {"request_id": uid(), "expected_revision": view["revision"],
                "condition": view["selected_condition"], "purpose": "sample", "exchange_id": 0})
            self.check("hidden_audio_blocked", False)
        except APIError as error:
            self.check("hidden_audio_blocked", error.code == "audio_hidden" and before == self.speech.counts, error_code=error.code)
        # At most one synthetic spoken clarification per condition; no retries.
        for condition in ("E", "A", "N", "S"):
            view = self.settle_comparison()
            branch = view["branches"][condition]
            if branch["status"] != "awaiting_clarification":
                continue
            self.cm("select", condition=condition)
            question = self.cv()["branches"][condition]["question"]
            answer = self.voice_input("comparison-answer-" + condition, "Yes, use only key points for all replies from now on, without explanations or examples.", "comparisons", condition, question["question_id"])
            self.cm("answer", branch=condition, question_id=question["question_id"], response={"text": answer})
        view = self.settle_comparison()
        self.save("comparison-first-reveal", view)
        self.check("comparison_all_results_revealed", view["results_visible"] and all(b["status"] == "ready" for b in view["branches"].values()), statuses={c:b["status"] for c,b in view["branches"].items()})
        if not view["results_visible"]:
            return
        first = deepcopy(view["first_reveal"])
        counts = {c:len(b["result"]["state"]["conversation"]) for c,b in view["branches"].items()}
        self.check("comparison_all_brief", all(b["result"]["state"]["settings"]["reply_length"] == "brief" for b in view["branches"].values()))
        query = self.voice_input("comparison-followup", "Give me one example of active recall for an English vocabulary quiz.", "comparisons", view["selected_condition"])
        self.cm("round_request", query=query)
        view = self.settle_comparison()
        self.save("comparison-latest-reveal", view)
        self.check("comparison_followup_all_four", view["results_visible"] and all(b["status"] == "ready" and len(b["result"]["state"]["conversation"]) == counts[c]+1 for c,b in view["branches"].items()))
        self.check("comparison_first_reveal_immutable", first == view["first_reveal"])
        self.cm("select", condition="S")
        self.play_reply("comparison-selective", "comparisons", "S")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly spend bounded real API calls")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; this verifier uses real provider quota")
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    report = {"kind": "engineering_acceptance_not_user_study", "input_source": "real_API_synthetic_TTS",
              "microphone_used": False, "provider_mode": "live", "retries": 0,
              "limits": {"input_tts": 15, "asr": 15, "output_tts": 10, "text_calls": 60},
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "limitations": ["No headset, microphone, human rating, subjective audio quality, or naturalistic participant behavior tested.",
                  "WAV validation proves a decodable provider payload, not perceived rate, tone, voice quality, or reply adequacy.",
                  "Uses real production service classes directly; Unity HTTP transport is verified separately."]}
    app = None
    try:
        config = literals(args.env_file)
        for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
            if config.get(key):
                os.environ[key] = config[key]
        teacher = Path.home() / ".config/aiaa4435/deepseek-teacher.key"
        if teacher.is_file():
            os.environ["DEEPSEEK_API_KEY"] = teacher.read_text().strip()
        os.environ.pop("DEEPSEEK_FALLBACK_API_KEY", None)
        model = BoundedModel(config.get("DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "")))
        speech = BoundedSpeech(SpeechConfig(config["QWEN_BASE_URL"], config["QWEN_API_KEY"],
                   config.get("QWEN_ASR_MODEL", "qwen-audio-3.0-asr-flash"), config.get("QWEN_TTS_MODEL", "qwen-audio-3.0-tts-plus"), 45))
        app = Acceptance(output, speech, model)
        app.run()
    except Exception as error:
        report["execution_error"] = {"type": type(error).__name__}
        if isinstance(error, (APIError, SpeechError)):
            report["execution_error"]["code"] = error.code
        print(json.dumps({"execution_error": report["execution_error"]}), flush=True)
    finally:
        if app:
            app.comparisons.shutdown(wait=True)
            report.update(checks=app.checks, speech_counts=app.speech.counts, model_call_count=len(app.model.calls),
                          speech_calls=app.speech.calls, model_calls=app.model.calls, inputs=app.inputs)
            app.save("final-session", app.session())
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["passed"] = bool(app and app.checks and not report.get("execution_error") and all(c["passed"] for c in app.checks))
        (output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"summary": str(output / "summary.json"), "passed": report["passed"]}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
