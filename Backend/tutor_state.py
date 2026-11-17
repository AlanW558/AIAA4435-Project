"""Tutor state foundation, used by tutor sessions; not yet connected to Unity.

Call commit only after a direct control or an approved policy decision. Proposed
edits and pending clarifications are owned by the future conversation controller.
No provider calls, audio, credentials, private study targets, or disk persistence.
"""
from __future__ import annotations

from copy import deepcopy
import math
import threading

from tutor_voice_catalog import DEFAULT_VOICE, VOICE_IDS
from capabilities import DEMO_PROFILE
from core import APIError, patch_valid, resolved_patch, text_value


SCHEMA_VERSION = "tutor-state-v3"
DIALOGUE_DEFAULTS = {
    "speech_rate": 1.0,
    "reply_length": "balanced",
    "tone": "professional",
    "voice": DEFAULT_VOICE,
}
DIALOGUE_OPTIONS = {
    "reply_length": ("brief", "balanced", "detailed"),
    "tone": ("professional", "friendly", "encouraging"),
    "voice": VOICE_IDS,
}
REPLY_LENGTH_GUIDANCE = {
    "brief": "Give only the key answer or essential points.",
    "balanced": "Give the key answer and a short supporting reason; omit a worked example.",
    "detailed": "Give the key answer, explain the reasoning, and add a relevant example or steps when useful.",
}
TONE_GUIDANCE = {
    "professional": "Use neutral, precise, composed wording. Be direct and respectful, without unnecessary formality or motivational praise.",
    "friendly": "Use warm, approachable, conversational wording. Express friendliness through phrasing, not extra greetings, praise, small talk or added explanation.",
    "encouraging": "Use supportive, constructive wording that makes another attempt feel manageable. Support effort and progress without assuming success, inventing praise, promising outcomes or adding a motivational paragraph.",
}
DEFAULT_SETTINGS = {**DIALOGUE_DEFAULTS, **DEMO_PROFILE.initial}
FIELDS = tuple(DEFAULT_SETTINGS)
COMMIT_SOURCES = ("direct_control", "request", "clarification")


def validate_patch(value):
    """Validate a partial edit without inferring intent or clamping invalid input."""
    if not isinstance(value, dict) or set(value) - set(FIELDS):
        raise APIError(400, "invalid_settings", "Only supported tutor setting fields are accepted.")
    result = deepcopy(value)
    for name, options in DIALOGUE_OPTIONS.items():
        if name in result and (not isinstance(result[name], str) or result[name] not in options):
            raise APIError(400, "invalid_settings", f"Unsupported {name} value.")
    if "speech_rate" in result:
        rate = result["speech_rate"]
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate):
            raise APIError(400, "invalid_settings", "Speech rate must be a finite multiplier.")
        # Match the existing Unity control: 0.70..1.30, precision 0.01. This is
        # an application setting, not a claim about any future TTS provider.
        nearest = round(rate, 2)
        if not .7 <= nearest <= 1.3 or abs(rate - nearest) > 1e-5:
            raise APIError(400, "invalid_settings", "Speech rate must be 0.70..1.30 in 0.01 increments.")
        result["speech_rate"] = nearest
    appearance = {key: result[key] for key in DEMO_PROFILE.fields if key in result}
    result.update(patch_valid(appearance, profile=DEMO_PROFILE))
    return result


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise APIError(400, "invalid_settings", "A complete tutor state requires every setting.")
    result = validate_patch(value)
    patch_valid({key: result[key] for key in DEMO_PROFILE.fields}, full=True, profile=DEMO_PROFILE)
    return result


class TutorState:
    """One isolated, in-memory session state with optimistic revision checking.

    Returned snapshots are detached. Revision counts accepted operations, not
    just visible changes. The controller must add HTTP idempotency and audit logs
    before exposing mutations to clients. This object alone is not a study API.
    """

    def __init__(self, settings=None):
        self._settings = validate_settings(DEFAULT_SETTINGS if settings is None else settings)
        self._task_start_settings = deepcopy(self._settings)
        self._revision = 0
        self._changes = []
        self._conversation = []
        self._lock = threading.RLock()

    def snapshot(self):
        with self._lock:
            return deepcopy({
                "schema_version": SCHEMA_VERSION,
                "revision": self._revision,
                "settings": self._settings,
                "task_start_settings": self._task_start_settings,
                "changes": self._changes,
                "conversation": self._conversation,
            })

    def capture_task_start(self):
        """Called only while preparing a NEW comparison, after public setup."""
        with self._lock:
            self._task_start_settings = deepcopy(self._settings)

    def _expect(self, revision):
        if type(revision) is not int or revision != self._revision:
            raise APIError(409, "stale_revision", "Refresh the tutor state before retrying.")

    def clone(self):
        """Detached working state for a controller transaction (including undo)."""
        with self._lock:
            other = TutorState(self._settings)
            other._task_start_settings = deepcopy(self._task_start_settings)
            other._revision = self._revision
            other._changes = deepcopy(self._changes)
            other._conversation = deepcopy(self._conversation)
            return other

    def commit(self, patch, *, expected_revision, source, query=""):
        with self._lock:
            self._expect(expected_revision)
            if source not in COMMIT_SOURCES:
                raise APIError(400, "invalid_source", "Unknown setting change source.")
            query = text_value(query, "query", 8000, empty=True)
            patch = validate_patch(patch)
            # Preserve the existing avatar replacement semantics, without
            # accidentally resetting any of the four dialogue properties.
            appearance = {key: patch[key] for key in DEMO_PROFILE.fields if key in patch}
            current_appearance = {key: self._settings[key] for key in DEMO_PROFILE.fields}
            patch.update(resolved_patch(current_appearance, appearance, DEMO_PROFILE))
            after = validate_settings({**self._settings, **patch})
            changed = {key: value for key, value in after.items() if self._settings[key] != value}
            self._revision += 1
            if changed:
                self._changes.append({
                    "id": self._revision, "kind": "commit", "source": source, "query": query,
                    "before": deepcopy(self._settings), "after": deepcopy(after),
                    "patch": changed, "remaining_fields": list(changed),
                })
            self._settings = after
            return self.snapshot()

    def undo(self, field, *, expected_revision):
        """Undo the latest eligible change to one field (or latest whole edit).

        Invalid combinations are rejected atomically, e.g. undoing only an avatar
        ID when the current outfit is unsupported by the restored avatar.
        """
        with self._lock:
            self._expect(expected_revision)
            if field not in (*FIELDS, "all"):
                raise APIError(400, "invalid_field", "Unknown undo field.")
            entry = next((item for item in reversed(self._changes)
                          if item["kind"] == "commit" and item["remaining_fields"]
                          and (field == "all" or field in item["remaining_fields"])), None)
            if entry is None:
                raise APIError(409, "nothing_to_undo", "No eligible change to undo.")
            fields = list(entry["remaining_fields"]) if field == "all" else [field]
            patch = {key: entry["before"][key] for key in fields}
            # Do not run replacement defaults here: undo restores exactly the
            # original values and must preserve all unrelated newer settings.
            after = validate_settings({**self._settings, **patch})
            before = deepcopy(self._settings)
            entry["remaining_fields"] = [key for key in entry["remaining_fields"] if key not in fields]
            self._revision += 1
            self._settings = after
            self._changes.append({
                "id": self._revision, "kind": "undo", "source": "undo",
                "target_change_id": entry["id"], "before": before, "after": deepcopy(after),
                "patch": patch, "remaining_fields": [],
            })
            return self.snapshot()

    def record_exchange(self, user_text, assistant_text, *, expected_revision, generation_settings=None):
        """Commit a successful tutor exchange against its generation revision.

        A provider failure must not call this method. If settings/history changed
        while generation was in flight, reject the obsolete result. Retain the
        generation settings so a later edit cannot relabel an earlier answer.
        An explicit validated job snapshot may include a one-answer override;
        recording that snapshot never changes the persistent settings.
        """
        with self._lock:
            self._expect(expected_revision)
            user_text = text_value(user_text, "user_text", 8000)
            assistant_text = text_value(assistant_text, "assistant_text", 16000)
            used_settings = validate_settings(self._settings if generation_settings is None else generation_settings)
            context_revision = self._revision
            self._revision += 1
            self._conversation.append({
                "id": self._revision, "context_revision": context_revision,
                "settings": used_settings,
                "messages": [{"role": "user", "content": user_text},
                             {"role": "assistant", "content": assistant_text}],
            })
            return self.snapshot()
