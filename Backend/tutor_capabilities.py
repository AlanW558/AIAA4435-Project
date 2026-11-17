"""Public interpretation capabilities, separate from connected runtime effects."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math

from capabilities import AVATAR_DEFAULTS, DEMO_PROFILE
from core import APIError, resolved_patch
from tutor_state import DIALOGUE_DEFAULTS, DIALOGUE_OPTIONS, FIELDS, validate_patch, validate_settings


CAPABILITY_VERSION = "tutor-capabilities-v2"
DIALOGUE_FIELDS = tuple(DIALOGUE_DEFAULTS)
APPEARANCE_FIELDS = tuple(DEMO_PROFILE.fields)
# Staged rollout: understanding a setting must not claim its output is connected.
EXECUTABLE_FIELDS = frozenset(FIELDS)
# The agreed panel has four dialogue controls, not an appearance editor.
CONTROL_FIELDS = frozenset(DIALOGUE_FIELDS)
AUDIO_AVAILABLE = False


class RateLimitError(ValueError):
    """Well-formed numeric intent outside the application's rate capability."""


def public_capabilities():
    return deepcopy({
        "version": CAPABILITY_VERSION,
        "options": {**DIALOGUE_OPTIONS, **DEMO_PROFILE.capabilities},
        "speech_rate": {"min": .70, "max": 1.30, "step": .01, "default": 1.0,
                        "basis": ["default", "current"], "operation": ["multiply", "add"]},
        "defaults": {**DIALOGUE_DEFAULTS, **DEMO_PROFILE.initial},
        "avatar_defaults": AVATAR_DEFAULTS,
        "outfits_by_avatar": {"liang": ["suit", "sport", "none"], "nailong": ["none"]},
        "voice_descriptions": {},
        "voice_resources_bound": False,
        "turn_fields": list(DIALOGUE_FIELDS),
    })


def resolve_rate(value, settings):
    """Calculate from the captured public baseline; never clamp or round intent."""
    if not isinstance(value, dict):
        # An absolute multiplier, including restored history. Keep the existing
        # float32 tolerance, but never silently approximate a requested value.
        try:
            return validate_patch({"speech_rate": value})["speech_rate"]
        except APIError:
            if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value):
                raise RateLimitError("Speech rate supports 0.70–1.30× default speed in steps of 0.01. Please choose a supported value; no settings were changed.") from None
            raise
    if set(value) != {"basis", "operation", "value"}:
        raise ValueError("Invalid rate expression")
    if value["basis"] not in ("default", "current") or value["operation"] not in ("multiply", "add"):
        raise ValueError("Invalid rate basis or operation")
    amount = value["value"]
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("Invalid rate operand")
    try:
        operand = Decimal(str(amount))
        base = Decimal("1.00") if value["basis"] == "default" else Decimal(str(settings["speech_rate"]))
        if not operand.is_finite() or (value["operation"] == "multiply" and operand <= 0):
            raise ValueError("Invalid rate operand")
        result = base * operand if value["operation"] == "multiply" else base + operand
        if not Decimal(".70") <= result <= Decimal("1.30"):
            raise RateLimitError("The requested speech rate is outside 0.70–1.30× default speed. Please choose a supported value; no settings were changed.")
        if result % Decimal(".01") != 0:
            raise RateLimitError("The requested speech rate cannot be represented in steps of 0.01. Please choose a supported value; no settings were changed.")
        return float(result)
    except InvalidOperation:
        raise ValueError("Invalid rate expression") from None


def candidate_patch(raw, settings, requested, required, preserved):
    """Expand avatar effects, enforce conjunctions/keep constraints, then diff."""
    if not isinstance(raw, dict) or set(raw) - set(FIELDS):
        raise ValueError("Invalid patch")
    patch = deepcopy(raw)
    if "speech_rate" in patch:
        patch["speech_rate"] = resolve_rate(patch["speech_rate"], settings)
    patch = validate_patch(patch)
    # Explicit conjunctions must be represented, including requested no-ops.
    # Legacy single-field {} is retained for the existing reply-length protocol.
    if set(required) - set(patch) and not (not patch and len(requested) == 1):
        raise ValueError("Candidate dropped a required property")
    allowed = set(requested) | set(preserved)
    if "avatar_id" in requested:
        allowed.update(APPEARANCE_FIELDS)
    if set(patch) - allowed:
        raise ValueError("Candidate edits an unrequested property")
    appearance = {f: patch[f] for f in APPEARANCE_FIELDS if f in patch}
    # Explicitly preserved appearance fields override avatar replacement defaults.
    if "avatar_id" in patch:
        appearance.update({f: settings[f] for f in preserved if f in APPEARANCE_FIELDS})
    # Reject a contradictory explicit value before the keep override can hide it.
    if any(f in patch and patch[f] != settings[f] for f in preserved):
        raise ValueError("Candidate violates a keep constraint")
    patch.update(resolved_patch({f: settings[f] for f in APPEARANCE_FIELDS}, appearance, DEMO_PROFILE))
    after = validate_settings({**settings, **patch})
    if any(after[f] != settings[f] for f in preserved):
        raise ValueError("Expanded candidate violates a keep constraint")
    changed = {f: after[f] for f in FIELDS if after[f] != settings[f]}
    # Keep full appearance fields when avatar_id is present: committing a sparse
    # avatar patch would otherwise reapply defaults and lose preserved values.
    if "avatar_id" in patch and changed:
        changed.update({f: after[f] for f in APPEARANCE_FIELDS})
    return changed, tuple(after[f] for f in FIELDS)


def execution_connected(interpretation):
    """Protect runtime routes until subsequent steps connect actual effects."""
    return set(interpretation["requested_fields"]) <= EXECUTABLE_FIELDS
