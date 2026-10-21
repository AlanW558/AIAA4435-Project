#!/usr/bin/env python3
"""Hash the actual Linux player payload, excluding build logs and this manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2] / 'Builds/AppearanceLinux'
files = [root / 'AppearanceLab.x86_64', root / 'UnityPlayer.so']
files += sorted((root / 'AppearanceLab_Data').rglob('*'))
files += sorted((root / 'MonoBleedingEdge').rglob('*'))
records = []
for p in files:
    if not p.is_file():
        continue
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    records.append({'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()})
if not records or not (root / 'AppearanceLab.x86_64').is_file():
    raise SystemExit('Build the player first.')
records.sort(key=lambda r: r['path'])
digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
manifest = {'algorithm': 'sha256(sorted payload file records)', 'build_sha256': digest, 'files': records}
(root / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'build_sha256': digest, 'files': len(records)}))
