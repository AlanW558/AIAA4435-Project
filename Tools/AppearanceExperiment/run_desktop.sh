#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$project_dir/StudyData"
if ! python3 -c 'import urllib.request,json; h=json.load(urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=2)); assert h["mode"]=="live"' 2>/dev/null; then
  nohup bash "$project_dir/Tools/AppearanceExperiment/start_backend.sh" >> "$project_dir/StudyData/backend-console.log" 2>&1 < /dev/null &
  backend_pid=$!
  for attempt in $(seq 1 30); do
    if python3 -c 'import urllib.request,json; h=json.load(urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=1)); assert h["mode"]=="live"' 2>/dev/null; then break; fi
    if ! kill -0 "$backend_pid" 2>/dev/null; then echo "Backend failed; see StudyData/backend-console.log" >&2; exit 1; fi
    sleep .2
  done
fi
export DISPLAY="${DISPLAY:-:1}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
exec bash "$project_dir/Tools/AppearanceExperiment/start_client.sh" "$@"
