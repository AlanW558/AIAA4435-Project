"""Default text evidence embedded in the existing durable audit transaction.

No audio, provider prompts, credentials or private targets are copied. A generated
answer is not a claim of delivery: checkpoints/reveal/presentation are separate.
"""
from copy import deepcopy
import hashlib
import json

VERSION = "tutor-dialogue-v1"
META = ("timestamp_utc", "monotonic_seconds", "run_id", "participant_id", "phase", "mode",
        "task_id", "task_code", "domain", "scenario", "series_id", "sequence_index",
        "session_id", "condition", "request_id", "revision", "engine_revision", "ticket_revision")


def input_fields(operation, data):
    """Bounded exact submitted strings; never turn a button label into speech."""
    keys = {"request": ("query", "question_id"), "answer": ("question_id", "option_id", "free_text")}.get(operation, ())
    return {k: data[k] for k in keys if isinstance(data.get(k), str) and len(data[k]) <= (8000 if k in ("query", "free_text") else 80)}


def annotate(record):
    """Pure projection: kept on the same JSONL line as its authoritative event."""
    event = record.get("engine_event") if record.get("event") == "engine_event" else record.get("event")
    entries = []
    scope = record.get("condition") or "shared"
    identity = [record.get("run_id"), record.get("task_id") or record.get("session_id"), scope]

    def add(role, kind, text=None, key=None, **fields):
        item = {"role": role, "kind": kind, "scope": scope, **fields}
        if text is not None:
            if not isinstance(text, str) or not text.strip():
                return
            item["text"] = text  # Preserve the submitted text, not the model's rewritten query.
            item["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        encoded = json.dumps([identity, kind, key, text], sort_keys=True, ensure_ascii=False)
        item["entry_id"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        entries.append(item)

    if event in ("command_received", "operation_started"):
        op = record.get("operation")
        data = record.get("data", {}) if event == "command_received" else record.get("input", {})
        rid = record.get("request_id")
        if op in ("start", "request", "round_request") and isinstance(data.get("query"), str):
            add("participant", "request", data.get("query"), key=rid, status="received_not_acceptance", input_source="submitted_text", question_id=data.get("question_id"))
        elif op == "answer":
            response = data.get("response", {}) if event == "command_received" else data
            response = response if isinstance(response, dict) else {}
            text = response.get("text", response.get("free_text"))
            if isinstance(text, str) and text.strip():
                add("participant", "clarification_answer", text, key=rid, status="received_not_acceptance", input_source="submitted_text", question_id=data.get("question_id"), option_id=response.get("option_id"))
            elif response.get("option_id"):
                add("participant", "option_selection", key=rid, status="received_not_acceptance", input_source="button", question_id=data.get("question_id"), option_id=response["option_id"])
    elif event == "answer_generated":
        add("tutor", "answer", record.get("answer"), key=record.get("job_id"), status="generated_not_presentation", origin="model",
            job_id=record.get("job_id"), exchange_id=record.get("exchange_id"), settings=record.get("settings"), response_kind=record.get("response_kind", "answer"))
    elif event in ("operation_committed", "branch_checkpoint"):
        result = record.get("result", {})
        question = result.get("question") or {}
        qid = question.get("question_id")
        if qid:
            add("tutor", "clarification", question.get("text"), key=qid, status="checkpointed_not_presentation", origin="controller",
                question_id=qid, options=deepcopy(question.get("options", [])))
        if result.get("decision") in ("ACT", "UNRESOLVED", "CANCELLED"):
            add("tutor", "setting_message", result.get("message"), key=record.get("request_id") or record.get("ticket_revision"),
                status="checkpointed_not_presentation", origin="controller")
        add("evidence", "checkpoint", key=[record.get("request_id"), result.get("revision")],
            state_revision=result.get("state_revision"), session_revision=result.get("revision"),
            processing_branch_revision=record.get("ticket_revision"), question_id=qid,
            completed_answers=[{"job_id": j["job_id"], "exchange_id": j.get("exchange_id"),
                                "text_sha256": hashlib.sha256(j["answer"].encode("utf-8")).hexdigest()}
                               for j in result.get("generation_jobs", []) if j.get("status") == "completed" and isinstance(j.get("answer"), str)],
            queued_job_ids=[j["job_id"] for j in result.get("generation_jobs", []) if j.get("status") == "queued"],
            completed_job_ids=[j["job_id"] for j in result.get("generation_jobs", []) if j.get("status") == "completed"])
    elif event in ("first_reveal", "round_reveal"):
        snapshot = record.get("snapshot", {})
        reveal = snapshot.get("first_reveal") or snapshot
        add("evidence", event, key=reveal.get("reveal_id"),
            round_index=reveal.get("round_index", 1),
            reveal_id=reveal.get("reveal_id"), task_revision=reveal.get("task_revision"),
            branches={c: {"branch_revision": b.get("branch_revision"),
                          "state_revision": b.get("state", {}).get("revision"),
                          "exchange_ids": [e.get("id") for e in b.get("state", {}).get("conversation", [])]}
                      for c, b in reveal.get("branches", {}).items()})
    elif event == "panel_presented":
        add("evidence", "panel_presented", key=[record.get("request_id"), record.get("monotonic_seconds")],
            page=record.get("page"), results_visible=record.get("results_visible"), branch_revision=record.get("branch_revision"),
            state_revision=record.get("state_revision"), reveal_id=record.get("reveal_id"))
    elif event in ('shared_settings_updated', 'preparation_confirmed'):
        add('evidence', event, key=record.get('request_id'), baseline=deepcopy(record.get('baseline')))
    elif event in ('audio_requested', 'audio_ready', 'audio_failed', 'audio_discarded'):
        add('evidence', event, key=[record.get('audio_request_id'), event],
            **{k: deepcopy(record[k]) for k in ('audio_request_id', 'purpose', 'exchange_id', 'question_id', 'expected_revision',
               'branch_revision', 'state_revision', 'reveal_id', 'text_sha256', 'speech_settings', 'cache_hit',
               'audio_duration_seconds', 'settings_scope', 'error') if k in record})
    elif event == 'playback_report':
        add('evidence', 'playback_report', key=(record.get('report') or {}).get('event_id'),
            **{k: deepcopy(record[k]) for k in ('audio_request_id', 'purpose', 'exchange_id', 'question_id', 'expected_revision',
               'branch_revision', 'state_revision', 'reveal_id', 'text_sha256', 'speech_settings', 'audio_duration_seconds',
               'evidence_source', 'receipt_run_id', 'report', 'settings_scope') if k in record})
    elif event == "strategy_preference_submitted":
        add("evidence", "strategy_preference", key=(record.get("preference") or {}).get("submission_id"), preference=deepcopy(record.get("preference")))
    elif event in ("preference_paused", "preference_resumed", "preference_exited"):
        add("evidence", event, key=record.get("request_id"))
    elif event == "feedback_saved":
        add("evidence", "feedback", key=(record.get("draft") or {}).get("feedback_revision"), draft=deepcopy(record.get("draft")))
    elif event in ("operation_error", "branch_failed"):
        add("evidence", "failure", key=[record.get("request_id"), record.get("monotonic_seconds")], code=record.get("code", record.get("error")))
    if entries:
        record["dialogue_schema_version"] = VERSION
        record["dialogue_entries"] = entries
    return record


def export_rows(records):
    """Yield (line, record) evidence once per stable entry. Compatible old events can also be projected."""
    seen = set()
    for line, source in records:
        record = annotate(deepcopy(source)) if "dialogue_entries" not in source else source
        for entry in record.get("dialogue_entries", []):
            if entry["entry_id"] in seen:
                continue
            seen.add(entry["entry_id"])
            yield {"schema_version": VERSION, **{k: record[k] for k in META if k in record},
                   "source_line": line, "source_event": record.get("event"), **deepcopy(entry)}
