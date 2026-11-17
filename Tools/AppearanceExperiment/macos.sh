#!/usr/bin/env bash
# Local Mac entry points. No credentials or participant identities are embedded.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"
runtime="$project_dir/Tools/AppearanceExperiment/.runtime/macos"
python_bin="${APPEARANCE_PYTHON:-$runtime/bin/python3}"
unity_bin="${APPEARANCE_UNITY:-/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity}"
action="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
case "$action" in
  help)
    echo 'Usage: bash Tools/AppearanceExperiment/macos.sh {setup|check|speech-check|mock|live|editor|verify-unity|build-pico}'
    exit 0 ;;
  setup)
    bootstrap="${APPEARANCE_PYTHON:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
    [[ -x "$bootstrap" ]] || { echo 'Set APPEARANCE_PYTHON to Python 3.10+.' >&2; exit 1; }
    "$bootstrap" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
    [[ -x "$runtime/bin/python3" ]] || "$bootstrap" -m venv "$runtime"
    "$runtime/bin/python3" --version
    exit 0 ;;
esac
[[ -x "$python_bin" ]] || { echo 'Run macos.sh setup first.' >&2; exit 1; }
"$python_bin" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
export PATH="$(dirname "$python_bin"):$PATH"
mkdir -p StudyData/macos
case "$action" in
  speech-check)
    exec "$python_bin" Tools/AppearanceExperiment/check_speech_readiness.py "$@" ;;
  check)
    "$python_bin" -m unittest discover -s Backend/tests -q
    "$python_bin" -m unittest discover -s Tools/AppearanceExperiment/tests -q
    "$python_bin" -m unittest discover -s Docs/AppearanceExperiment/Study/tests -q
    "$python_bin" Tools/AppearanceExperiment/verify_source.py --out StudyData/macos/source-checks.json ;;
  mock)
    exec "$python_bin" Backend/server.py --mode mock --host 127.0.0.1 --port "${APPEARANCE_PORT:-8765}" --log-dir StudyData/macos/mock-logs "$@" ;;
  live)
    if [[ -z "${APPEARANCE_ENV_FILE:-}" && -f "$project_dir/.env" ]]; then
      export APPEARANCE_ENV_FILE="$project_dir/.env"
    fi
    export APPEARANCE_PYTHON="$python_bin"
    exec bash Tools/AppearanceExperiment/start_backend.sh "$@" ;;
  editor)
    [[ -x "$unity_bin" ]] || { echo 'Unity editor not found.' >&2; exit 1; }
    export APPEARANCE_PHASE=debug APPEARANCE_PARTICIPANT_ID=DEBUGMAC
    export APPEARANCE_STUDY_SESSION_ID="mac-debug-$(date +%Y%m%d-%H%M%S)"
    export APPEARANCE_ASSIGNED=0 APPEARANCE_TASK_ID=''
    export APPEARANCE_CONDITION="${APPEARANCE_CONDITION:-S}"
    export APPEARANCE_CAPABILITY_PROFILE="${APPEARANCE_CAPABILITY_PROFILE:-avatar-demo-v1}"
    export APPEARANCE_BACKEND_URL="${APPEARANCE_BACKEND_URL:-http://127.0.0.1:${APPEARANCE_PORT:-8765}}"
    exec "$unity_bin" -projectPath "$project_dir" -executeMethod AppearanceMacSetup.OpenDemo -logFile "$project_dir/StudyData/macos/editor.log" ;;
  verify-unity)
    exec "$unity_bin" -batchmode -quit -projectPath "$project_dir" -executeMethod AppearanceMacSetup.Verify -logFile "$project_dir/StudyData/macos/unity-verification.log" ;;
  build-pico)
    export APPEARANCE_UNITY="$unity_bin"
    exec bash Tools/AppearanceExperiment/build_pico.sh ;;
  *) echo "Unknown action: $action" >&2; exit 2 ;;
esac
