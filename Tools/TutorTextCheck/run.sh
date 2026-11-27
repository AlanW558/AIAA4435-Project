#!/usr/bin/env bash
# Researcher-operated auxiliary checks. No server/Unity/device changes.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${APPEARANCE_PYTHON:-$project_dir/Tools/AppearanceExperiment/.runtime/macos/bin/python3}"
[[ -x "$python_bin" ]] || { echo 'Set APPEARANCE_PYTHON to a Python 3.10+ executable.' >&2; exit 1; }
env_path="${APPEARANCE_ENV_FILE:-$project_dir/.env}"
[[ -f "$env_path" ]] || { echo 'Private model configuration is missing.' >&2; exit 1; }
set -a
source "$env_path"
set +a
teacher_key_path="${APPEARANCE_TEACHER_KEY_FILE:-$HOME/.config/aiaa4435/deepseek-teacher.key}"
if [[ -f "$teacher_key_path" ]]; then
  DEEPSEEK_API_KEY="$(<"$teacher_key_path")"
  export DEEPSEEK_API_KEY
fi
# No automatic second-account fallback in this auxiliary invocation.
unset DEEPSEEK_FALLBACK_API_KEY
cd "$project_dir"
exec "$python_bin" Tools/TutorTextCheck/batch.py "$@"
