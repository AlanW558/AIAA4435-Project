#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
env_path="${APPEARANCE_ENV_FILE:-$HOME/.config/aiaa4435/appearance.env}"
if [[ ! -f "$env_path" ]]; then
  echo "Missing private environment file: $env_path" >&2
  echo "Set DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL and DEEPSEEK_MODEL outside the repository." >&2
  exit 1
fi
set -a
source "$env_path"
set +a
exec python3 "$project_dir/Backend/server.py" --mode live --host 127.0.0.1 --port "${APPEARANCE_PORT:-8765}" --log-dir "$project_dir/StudyData/logs" "$@"
