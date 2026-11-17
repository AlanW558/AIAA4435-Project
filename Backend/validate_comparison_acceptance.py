#!/usr/bin/env python3
"""Read-only model audit of a completed local acceptance run; no provider calls."""
import argparse
from collections import Counter
import json
from pathlib import Path


def audit(folder):
    server = json.loads((folder / "server.json").read_text())
    report = {"scope": "Engineering audit only; not participant success or a clean unattended-run claim.",
              "mode": server["mode"], "requested_model": server["model"], "provider_attempts": server["provider_attempts"],
              "tasks": [], "checks": {}, "original_check_report": (folder / "checks.txt").read_text().splitlines()[0]}
    canonical = []
    for path in sorted((folder / "logs/comparisons/debug").glob("*.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        by_event = lambda name: [r for r in rows if r["event"] == name]
        shared, gates, reveals = by_event("shared_prepared"), by_event("branch_gate_plan"), by_event("first_reveal")
        started, finished = by_event("provider_started"), by_event("provider_finished")
        checks = {"one_shared_preparation": len(shared) == 1,
                  "one_initial_interpretation": sum(r["method"] == "interpret_tutor" and r["condition"] is None for r in started) == 1,
                  "all_gates_reference_same_shared_input": len(shared) == 1 and len(gates) == 4 and {r["condition"] for r in gates} == set("EANS") and len({r["shared_id"] for r in gates}) == 1 and gates[0]["shared_id"] == shared[0]["prepared"]["shared_id"],
                  "one_first_reveal": len(reveals) == 1,
                  "provider_records_paired": len({r["call_id"] for r in started}) == len(started) and Counter(r["call_id"] for r in started) == Counter(r["call_id"] for r in finished)}
        if len(reveals) == 1:
            first = reveals[0]
            prior = rows[:rows.index(first)]
            latest = {c: next((r for r in reversed(prior) if r["event"] == "branch_checkpoint" and r["condition"] == c), None) for c in "EANS"}
            checks["no_pending_question_or_generation_at_reveal"] = all(r and r["result"]["question"] is None and all(j["status"] == "completed" for j in r["result"]["generation_jobs"]) for r in latest.values())
            checks["revealed_snapshots_match_committed_checkpoints"] = all(r and all(first["snapshot"]["branches"][c]["state"][key] == r["result"][key] for key in ("settings", "changes", "conversation")) for c, r in latest.items())
            submissions = by_event("task_submitted")
            if submissions:
                s = submissions[0]["submission"]
                checks["single_submission_preserves_first_snapshot"] = len(submissions) == 1 and s["first_reveal"] == first["snapshot"]
                checks["feedback_matches_submitted_branch_versions"] = all(s["feedback"][c]["branch_revision"] == s["final_results"][c]["branch_revision"] for c in "EANS")
        calls = [record for r in finished for record in r["model_calls"]]
        canonical.extend(calls)
        report["tasks"].append({"task_id": path.stem, "sequence_index": rows[0]["sequence_index"], "checks": checks,
                                "provider_methods": dict(Counter(r["method"] for r in started)),
                                "first_lengths": {c: reveals[0]["snapshot"]["branches"][c]["state"]["settings"]["reply_length"] for c in "EANS"} if reveals else {},
                                "generation_references": len(by_event("generation_reference")),
                                "generation_reuses": sum(r["reused"] for r in by_event("generation_reference")),
                                "events": dict(Counter(r["event"] for r in rows))})
    report["checks"]["all_task_invariants"] = bool(report["tasks"]) and all(all(t["checks"].values()) for t in report["tasks"])
    if server["mode"] == "live":
        report["checks"].update({"canonical_attempt_count_matches_server": len(canonical) == server["provider_attempts"] == len(server["records"]),
                                  "within_attempt_cap": server["provider_attempts"] <= server["attempt_limit"],
                                  "all_provider_attempts_successful": all(r["status"] == "ok" for r in canonical)})
    report["response_models"] = sorted({r["response_model"] for r in canonical if r.get("response_model")})
    report["usage"] = {k: sum(r.get("usage", {}).get(k, 0) for r in canonical) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    report["invariants_passed"] = all(report["checks"].values())
    (folder / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    result = audit(parser.parse_args().run)
    print(json.dumps({"invariants_passed": result["invariants_passed"], "provider_attempts": result["provider_attempts"],
                      "tasks": len(result["tasks"]), "original_check_report": result["original_check_report"], "usage": result["usage"]}))
    raise SystemExit(0 if result["invariants_passed"] else 1)
