#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
unity_bin="${APPEARANCE_UNITY:-$HOME/Unity/Hub/Editor/2022.3.62f3c1/Editor/Unity}"
[[ -x "$unity_bin" ]] || { echo "Unity 2022.3.62f3c1 is required." >&2; exit 1; }
cd "$project_dir"
snapshot_dir="$(mktemp -d)"
settings=(Assets/Project/Settings/PicoURP.asset Assets/Resources/PXR_ProjectSetting.asset ProjectSettings/ProjectSettings.asset)
for index in "${!settings[@]}"; do cp -- "${settings[$index]}" "$snapshot_dir/$index"; done
restore_settings() {
  for index in "${!settings[@]}"; do cp -- "$snapshot_dir/$index" "${settings[$index]}"; done
  rm -r -- "$snapshot_dir"
}
trap restore_settings EXIT
mkdir -p Builds/Pico
"$unity_bin" -batchmode -quit -projectPath "$project_dir" -buildTarget Android \
  -executeMethod AppearanceVRSetup.BuildAndroid -logFile "$project_dir/Builds/Pico/appearance-editor-build.log"
python3 - <<'PY'
from pathlib import Path
import hashlib,json
apk=Path('Builds/Pico/AppearanceVR.apk')
status=json.loads(Path('Builds/Pico/AppearanceBuildStatus.json').read_text())
if status['result']!='Succeeded':raise SystemExit('Build was not successful.')
record={'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'bytes':apk.stat().st_size,'package':status['package'],'build_report':'AppearanceBuildStatus.json'}
Path('Builds/Pico/appearance-fingerprint.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
PY
