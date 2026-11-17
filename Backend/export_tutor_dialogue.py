"""Export default dialogue/evaluation evidence from one session/task audit JSONL."""
import argparse
import json
from pathlib import Path
from tutor_dialogue_log import export_rows


def export_file(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Output must not overwrite the source audit.")
    # Validate the entire source first; incomplete lines must not be silently skipped.
    records = [(i, json.loads(line)) for i, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1) if line.strip()]
    rows = [{"source_file": source.name, **row} for row in export_rows(records)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Existing task/session audit JSONL")
    parser.add_argument("destination", help="New JSONL path; never overwrites existing evidence")
    args = parser.parse_args()
    print(f"Exported {export_file(args.source, args.destination)} evidence rows.")
