#!/usr/bin/env python3
"""Validate a completed web download; preserve original data and explicit corrections."""
import argparse
from pathlib import Path
from data_contract import import_participant, read

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--participant-id', required=True)
    parser.add_argument('--display-label', required=True)
    parser.add_argument('--review-data', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, default=Path(__file__).resolve().parents[1] / 'results')
    parser.add_argument('--amendments', type=Path, help='Explicit corrections only; never inferred from unable_to_judge.')
    parser.add_argument('--provenance', type=Path)
    args = parser.parse_args()
    try:
        path, created = import_participant(args.file, args.participant_id, args.display_label, args.review_data,
            args.output_directory, read(args.amendments) if args.amendments else None,
            read(args.provenance) if args.provenance else None)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Import rejected: {error}\n')
    print(f'{"Created" if created else "Already imported, unchanged"}: {path.name}')

if __name__ == '__main__':
    main()
