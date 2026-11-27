#!/usr/bin/env bash
# Thin wrapper: strategy logic, release barrier and TTS stay in Tools/Backend.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# -lt 2 ]]; then
  echo 'Usage: run_api.sh BATCH_DIRECTORY status|sync|process|publish|... [arguments]' >&2
  exit 2
fi
batch_directory="$(cd -- "$1" && pwd)"
shift
[[ -f "$batch_directory/TASK_REQUESTS.md" ]] || { echo 'Prepare and fill TASK_REQUESTS.md first.' >&2; exit 1; }
# No implicit old default directory/workbook; no keys are printed or copied.
exec bash "$project_dir/Tools/TutorTextCheck/run.sh" \
  --directory "$batch_directory" --workbook "$batch_directory/TASK_REQUESTS.md" "$@"
