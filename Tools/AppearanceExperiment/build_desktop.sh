#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
unity_bin="${APPEARANCE_UNITY:-$HOME/Unity/Hub/Editor/2022.3.62f3c1/Editor/Unity}"
if [[ ! -x "$unity_bin" ]]; then echo "Set APPEARANCE_UNITY to Unity 2022.3.62f3c1." >&2; exit 1; fi
cd "$project_dir"
snapshot_dir="$(mktemp -d)"
# Unity/PICO writes these during import/build; preserve the caller's exact files.
settings=(Assets/Project/Settings/PicoURP.asset Assets/Resources/PXR_ProjectSetting.asset ProjectSettings/ProjectSettings.asset Assets/Project/Scenes/AppearanceExperiment.unity)
for index in "${!settings[@]}"; do cp -- "${settings[$index]}" "$snapshot_dir/$index"; done
restore_settings() {
  for index in "${!settings[@]}"; do cp -- "$snapshot_dir/$index" "${settings[$index]}"; done
  rm -r -- "$snapshot_dir"
}
trap restore_settings EXIT
mkdir -p Builds/AppearanceLinux
"$unity_bin" -batchmode -quit -projectPath "$project_dir" -buildTarget Linux64 \
  -executeMethod AppearanceExperimentSetup.BuildLinux -logFile "$project_dir/Builds/AppearanceLinux/editor-build.log"
python3 Tools/AppearanceExperiment/fingerprint_build.py
