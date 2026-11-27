#!/usr/bin/env python3
"""Create a fresh editable task worksheet. Never copy results or overwrite a batch."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/TutorTextCheck'))
import workbook

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if directory.exists():
        parser.error('Choose a new directory; existing batches are immutable input evidence.')
    # Source task layout and display numbering come from the authoritative catalog.
    directory.mkdir(parents=True)
    workbook.generate(directory / 'TASK_REQUESTS.md')
    print(f'Prepared {directory.name}/TASK_REQUESTS.md; no API calls. Fill requests before running.')

if __name__ == '__main__':
    main()
