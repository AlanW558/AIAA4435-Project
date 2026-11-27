# Invalid model-candidate recovery — 2026-11-28

## Problem and scope

The v4 outcome audit found that an ambiguous request such as “I want a different feel to the way you speak.” could finish as `UNRESOLVED` in all four conditions without offering a clarification. The normalized evidence reported an unrepresentable speech-rate suggestion. The earlier normalizer caught any `RateLimitError`, discarded **all** candidates and ambiguity metadata, and marked the entire proposal unsupported. The common unsupported gate then ran before Always Ask or Selective could ask.

This change repairs that validation/recovery path only. It does not revise the 32 requests, questionnaires, v4 outcomes, ratings, audio, or prior clarification counts. It does not repair the separate R1-2 relative-rate execution issue. No paid model or TTS calls were made.

The original provider JSON for the audited V3-1 failure is unavailable. The new tests use explicit synthetic responses with the same failure shape; they are **not an exact replay** of the original model output and are not evidence of live model accuracy.

## New behavior

The interpreter and common gate are now `tutor-interpretation-v9` and `tutor-gates-v4`.

1. Each candidate is validated independently. If a candidate has an unsupported numeric speech-rate suggestion, the **whole candidate** is set aside. The code never rounds/clamps the rate, removes just the invalid field, or executes a partial conjunctive request.
2. Recovery requires public evidence of uncertainty and no explicit numeric wording in the current public utterance. Evidence can be either retained `ambiguities` involving speech rate, or alternatives spanning different attribute sets with at least one fully valid candidate. The latter supports cases where the model omitted `ambiguities`.
3. Valid candidates, required/preserved fields, scope, and existing ambiguity evidence survive. An internal `candidate_recovery` record identifies rejected candidate IDs and validation reasons. The model cannot submit this internal field.
4. Recovery produces a shared open clarification. If valid candidates remain, the participant may choose one or explain another change. If all candidates are invalid but public uncertainty is retained, the question offers only `other` and `cancel`; no replacement candidate or default is invented.
5. The public pending-question contract now permits zero to three concrete candidates, followed by `other` and `cancel`. Free-text answers use the existing bound-answer interpreter and resolver. A clear supported resolution applies only its validated patch, while original keep constraints continue to hold. An unsupported or still-ambiguous answer leaves the question available for another answer or cancellation.

### Common recovery versus experimental policy

`COMMON_CANDIDATE_RECOVERY` is a **common validation fallback**, not a new ordinary strategy rule. It yields `ASK` in E/A/N/S so that no condition automatically executes an invalid suggestion or a surviving guess after filtering. Native does not make an additional paid decision in this fallback.

Normal Execute-first requests still follow `EXECUTE_FIRST`; normal Always Ask and Selective decisions remain their existing policies. Therefore a recovery question must not be described as evidence that Execute-first ordinarily asks or that Selective independently detected the ambiguity.

Existing session `gate_decision` and comparison `branch_gate_plan` logs record the distinct reason and current policy version. The normalized interpretation retains `candidate_recovery.rejected_candidates` for audit. Future analyses should identify these common recovery events separately from ordinary policy-driven clarification. The existing v4 audit and its 46 clarification events are unchanged.

## Boundaries and safety properties

- Explicit numeric requests, including English spoken numbers, percentages and the common fraction/multiplier forms recognized by the conservative guard, keep the strict unsupported-value path. For example, `1.0925×`, “one point zero nine two five,” or “five percent slower” from `1.15×` are never replaced by `1.09×` or another supported alternative.
- The numeric-word guard is a conservative exclusion check, not a general natural-language arithmetic parser. A numeral elsewhere in the request can also prevent automatic recovery. This can cause an unnecessary `UNRESOLVED`, but cannot authorize an approximate setting. Interpretation of arbitrary paraphrases and other languages still depends on the interpreter; this change does not claim universal numeric-language coverage.
- When all candidates are invalid and neither explicit ambiguity metadata nor a validated cross-attribute alternative supplies uncertainty evidence, the request remains `UNRESOLVED`. A single illegal model suggestion is not automatically reclassified as a qualitative user request.
- Malformed schema, unknown categorical values, unsupported fields, missing required conjuncts, contradictory keep constraints, and invalid candidate IDs retain their existing strict validation. This change handles numeric rate capability errors, not arbitrary malformed model output.
- No task code, study goal, private target interval, questionnaire rating, or strategy label is used to decide recovery. Candidate generation continues to receive only its existing public context.
- Matching a final setting does not prove perceived audio quality or successful participant intent recognition. These tests validate the recovery contract, not subjective study outcomes.

## Files changed

- `Backend/tutor_interpretation.py`: per-candidate numeric rejection, conservative recovery boundary, internal diagnostics, two-option open pending questions, interpreter version.
- `Backend/tutor_policy.py`: shared recovery gate, open question wording, policy version.
- `Backend/tutor_session.py`: prevent an incompletely recovered free-text interpretation from being committed.
- `Backend/tests/test_tutor_candidate_recovery.py`: 12 new offline regressions.
- `Backend/tests/test_tutor_ambiguity_contract.py`: current version assertions and updated regression for optional invalid rate suggestions.

Both the single Selective session and shared comparison preparation use these same interpreter/gate functions. No Unity, `study*`, or `Tools/TutorTextCheck` files were changed for this fix.

## Validation

Executed with `Tools/AppearanceExperiment/.runtime/macos/bin/python3`; all model adapters in these tests are fixtures.

- New recovery suite: **12/12 passed**. Covers a valid tone/voice choice plus illegal inferred rate, invalid default, all-invalid open questions, no-ambiguities cross-attribute recovery, the conservative all-invalid/no-evidence boundary, exact unsupported numeric requests, required-field retention, malformed data rejection, shared inputs without private task identity, single-session full-text clarification, unsupported answers followed by a valid answer, and four comparison branches waiting until every answer is resolved before revealing results.
- Broader `test_tutor_*.py` discovery: **384 tests**. The sandbox run passed 376; eight localhost HTTP tests were blocked solely by `PermissionError` when binding temporary loopback ports. Those eight were rerun with approved local-port access and **all eight passed**. There were no remaining test failures.
- `git diff --check` passed for the changed backend and test files.

Commands:

```sh
Tools/AppearanceExperiment/.runtime/macos/bin/python3 -m unittest discover -s Backend/tests -p test_tutor_candidate_recovery.py -v
Tools/AppearanceExperiment/.runtime/macos/bin/python3 -m unittest discover -s Backend/tests -p 'test_tutor_*.py' -q
```

The isolated HTTP rerun, from `Backend/tests`, used the seven test classes containing the eight blocked tests: `AudioHTTPTests`, `HttpTests`, `GenerationHTTPTests`, `LifecycleHttpTests`, `TutorHTTPTests`, `SpeechSettingsHTTPTests`, and `TranscriptionHTTPTests`.

No API live rerun, subjective audio evaluation, Unity/VR test, or Git commit is included in this change.
