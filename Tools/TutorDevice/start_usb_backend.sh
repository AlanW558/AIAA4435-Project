#!/usr/bin/env bash
# Stable, separate engineering data directory for USB headset tests.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${APPEARANCE_PYTHON:-$project_dir/Tools/AppearanceExperiment/.runtime/macos/bin/python3}"
[[ -x "$python_bin" ]] || { echo 'Set APPEARANCE_PYTHON to a Python 3.10+ executable.' >&2; exit 1; }
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
export APPEARANCE_PYTHON="$python_bin"
export APPEARANCE_ENV_FILE="${APPEARANCE_ENV_FILE:-$project_dir/.env}"
export APPEARANCE_PORT="${APPEARANCE_PORT:-8765}"
data_dir="${TUTOR_USB_DATA_DIR:-$project_dir/StudyData/device-usb/backend}"
cd "$project_dir"
exec bash Tools/AppearanceExperiment/start_backend.sh \
  --speech-mode qwen --timeout 45 --log-dir "$data_dir" "$@"
