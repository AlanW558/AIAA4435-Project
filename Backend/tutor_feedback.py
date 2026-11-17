"""Versioned debug feedback contract. No survey data enter tutor/model contexts."""
from copy import deepcopy
from core import APIError, text_value

FEEDBACK_VERSION = "task-feedback-q1-q7-v1"
COMPLETION = {"fully_met", "partly_met", "not_met", "unable_to_judge"}
ATTRIBUTE_VERSION = "attribute-feedback-v2"
NATURAL_VERSION = "natural-selective-feedback-v1"
ATTRIBUTE_RATINGS = ("effort_ease", "control", "clarification_appropriateness", "satisfaction")
RATINGS = ("q2", "q3", "q4", "q5", "q6", "q7")
REASONS = {"target_mismatch", "unwanted_change", "not_maintained", "hard_to_verify", "interaction_problem", "other"}


def validate_feedback(value, *, later_interaction=False, version=FEEDBACK_VERSION):
    fields, category = specification(version)
    if not isinstance(value, dict) or set(value) - ({category, "ratings", "comment", "comment_confirmed"} | ({"reasons"} if version != NATURAL_VERSION else set())):
        raise APIError(400, "invalid_feedback", "Use structured answers and confirmed text only; audio is not accepted.")
    result = {}
    if category in value:
        if not isinstance(value[category], str) or value[category] not in COMPLETION:
            raise APIError(400, "invalid_completion", "Choose a completion category, not a numeric score.")
        result[category] = value[category]
    ratings = value.get("ratings", {})
    if not isinstance(ratings, dict) or set(ratings) - set(fields):
        raise APIError(400, "invalid_ratings", "Use only the rating fields for this questionnaire version.")
    for rating in ratings.values():
        if not (type(rating) is int and 1 <= rating <= 7) and rating != "unable_to_judge":
            raise APIError(400, "invalid_rating", "Explicitly choose 1–7 or unable_to_judge; missing answers remain missing.")
    result["ratings"] = deepcopy(ratings)
    reasons = value.get("reasons", [])
    if not isinstance(reasons, list) or any(not isinstance(r, str) or r not in REASONS for r in reasons) or len(set(reasons)) != len(reasons):
        raise APIError(400, "invalid_reasons", "Use unique reason codes.")
    # Hide and discard reasons when Q1 makes them inapplicable; never silently
    # submit old selections after the participant changes their completion answer.
    result["reasons"] = reasons if result.get("completion") in COMPLETION - {"fully_met"} else []
    if not later_interaction:
        result["reasons"] = [r for r in result["reasons"] if r != "not_maintained"]
    if version == NATURAL_VERSION:
        result.pop("reasons", None)
    comment = text_value(value.get("comment", ""), "comment", 4000, empty=True)
    if "comment_confirmed" in value and type(value["comment_confirmed"]) is not bool:
        raise APIError(400, "invalid_confirmation", "Text confirmation must be explicit.")
    if comment and value.get("comment_confirmed") is not True:
        raise APIError(400, "unconfirmed_comment", "Confirm the optional transcription before saving it.")
    result["comment"] = comment
    result["comment_confirmed"] = bool(comment)
    return result


def specification(version):
    if version == FEEDBACK_VERSION:
        return RATINGS, "completion"
    if version == ATTRIBUTE_VERSION:
        return ATTRIBUTE_RATINGS, "completion"
    if version == NATURAL_VERSION:
        return ATTRIBUTE_RATINGS + ("interruption",), "goal_fit"
    raise APIError(400, "invalid_feedback_version", "Use a supported questionnaire version.")


def complete(answers, version=FEEDBACK_VERSION):
    fields, category = specification(version)
    return answers.get(category) in COMPLETION and set(answers.get("ratings", {})) == set(fields)
