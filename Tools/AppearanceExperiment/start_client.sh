#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
client="$project_dir/Builds/AppearanceLinux/AppearanceLab.x86_64"
if [[ ! -x "$client" ]]; then
  echo "Build the Linux player using AIAA4435 > Appearance > Build Linux desktop experiment." >&2
  exit 1
fi
mkdir -p "$project_dir/StudyData/client-logs"
mkdir -p "$project_dir/StudyData/captures"
python3 "$project_dir/Tools/AppearanceExperiment/fingerprint_build.py"
export APPEARANCE_BUILD_SHA256
APPEARANCE_BUILD_SHA256="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_sha256"])' "$project_dir/Builds/AppearanceLinux/build-manifest.json")"
export APPEARANCE_CAPTURE_DIR="${APPEARANCE_CAPTURE_DIR:-$project_dir/StudyData/captures}"
exec "$client" -screen-width 1440 -screen-height 900 -screen-fullscreen 0 -logFile "$project_dir/StudyData/client-logs/player-$(date -u +%Y%m%dT%H%M%S).log" "$@"
