#!/usr/bin/env python3
"""Rebuild aggregation from distinct validated participant files, without model calls."""
import argparse
from pathlib import Path
from data_contract import aggregate, atomic_json, read

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'results')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = aggregate([read(p) for p in sorted(args.directory.glob('participant_[0-9]*.json'))])
    destination = args.output or args.directory / 'aggregate_results.json'
    atomic_json(destination, result)
    print(f'{result["n_unique_participants"]} participants; {len(result["cohorts"])} separate cohorts; {destination.name}')

if __name__ == '__main__':
    main()
