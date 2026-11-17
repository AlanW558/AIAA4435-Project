"""Bounded, explicitly invoked interactive sample preparation, not a runtime adapter.

Default is offline. --execute makes at most 15 TTS calls, no retries/fallback.
Existing evidence prevents accidental repeat charges. Secrets/URLs are never logged.
"""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import shlex
import urllib.error
import urllib.parse
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / 'Docs/TutorPersonalization/STAGE_4_SPEECH_PROFILE.json'
OUT = ROOT / 'StudyData/validation/stage4-speech-step1-20261110'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Continue only never-attempted cases')
    parser.add_argument('--limit', type=int, default=15)
    parser.add_argument('--profile', type=Path, default=PROFILE)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    OUT = args.output.resolve()
    if not OUT.is_relative_to((ROOT / 'StudyData/validation').resolve()):
        raise SystemExit('Output must be inside StudyData/validation.')
    profile = json.loads(args.profile.read_text())
    variants = [('professional', 1.0)] if args.baseline_only else [('professional', 1.0), ('friendly', 1.0), ('encouraging', 1.0), ('professional', .7), ('professional', 1.3)]
    cases = []
    for slot, voice in profile['voices'].items():
        for tone, rate in variants:
            name = f'{slot}_{tone}_{rate:.2f}'
            payload = {'model': profile['tts_model'], 'input': {
                **profile['fixed_parameters'], 'voice': voice['provider_id'],
                'text': profile['sample_text'], 'rate': rate,
                'instruction': profile['tone_instructions'][tone]}}
            cases.append({'id': name, 'voice': slot, 'tone': tone, 'rate': rate, 'payload': payload})
    if not 0 < len(cases) <= 15:
        raise SystemExit('Use --baseline-only or at most three voices for a full comparison (15-call cap).')
    assert len({c['id'] for c in cases}) == len(cases)
    if not args.execute:
        print(json.dumps({'mode': 'offline', 'requests_planned': len(cases), 'characters_planned': len(profile['sample_text']) * len(cases), 'output': str(OUT)}))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = OUT / 'results.json'
    if evidence.exists() and not args.resume:
        raise SystemExit('Existing evidence found; refusing to repeat paid calls.')
    config = {}
    for line in (ROOT / '.env.qwen-token-plan').read_text().splitlines():
        if line and not line.startswith('#'):
            k, v = line.split('=', 1)
            config[k] = shlex.split(v)[0]
    key = config['TOKEN_PLAN_API_KEY']
    base = config['QWEN_TOKEN_PLAN_BASE_URL']
    if base != 'https://token-plan.cn-beijing.maas.aliyuncs.com':
        raise SystemExit('Unexpected provider endpoint; review before sending credentials.')
    client = urllib.request.build_opener(NoRedirect)
    previous = json.loads(evidence.read_text()) if evidence.exists() else None
    if previous and previous['profile'] != profile:
        raise SystemExit('Profile differs from existing evidence; refusing mixed results.')
    records = previous['records'] if previous else []
    report = {'profile': profile, 'records': records, 'listening_status': 'not_reviewed', 'maximum_calls': len(cases)}
    evidence.write_text(json.dumps(report, indent=2))
    attempted = {r['id'] for r in records}
    remaining = [c for c in cases if c['id'] not in attempted][:max(0, min(args.limit, 15))]
    for case in remaining:
        row = {**case, 'status': 'attempting'}
        records.append(row)
        evidence.write_text(json.dumps(report, indent=2))
        req = urllib.request.Request(base + '/api/v1/services/audio/tts/SpeechSynthesizer',
            data=json.dumps(case['payload']).encode(), method='POST',
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with client.open(req, timeout=45) as response:
                row['http_status'] = response.status
                data = json.load(response)
            row.update(request_id=data.get('request_id'), usage=data.get('usage'))
            url = data.get('output', {}).get('audio', {}).get('url')
            row['returned_audio_scheme'] = urllib.parse.urlparse(url or '').scheme
            if url and row['returned_audio_scheme'] == 'http':
                url = urllib.parse.urlparse(url)._replace(scheme='https').geturl()
            if not url or urllib.parse.urlparse(url).scheme != 'https':
                raise ValueError('Missing HTTPS generated audio URL')
            # Separate request deliberately has no Authorization header.
            with client.open(urllib.request.Request(url), timeout=45) as audio_response:
                audio = audio_response.read(5_000_001)
            if len(audio) > 5_000_000:
                raise ValueError('Unexpected sample size')
            with wave.open(io.BytesIO(audio)) as wav:
                row['audio_format'] = {'channels': wav.getnchannels(), 'sample_rate': wav.getframerate(), 'sample_width': wav.getsampwidth()}
                if not wav.getnframes():
                    raise ValueError('Empty WAV')
            filename = case['id'] + '.wav'
            (OUT / filename).write_bytes(audio)
            row.update(status='audio_saved', file=filename, bytes=len(audio), sha256=hashlib.sha256(audio).hexdigest())
        except urllib.error.HTTPError as exc:
            row.update(status='http_error', http_status=exc.code)
            # Deliberately omit raw error bodies, URLs and request headers.
        except Exception as exc:
            row.update(status='error', error_type=type(exc).__name__)
        evidence.write_text(json.dumps(report, indent=2))
        print(case['id'], row['status'], row.get('http_status'), flush=True)
        if row['status'] != 'audio_saved':
            break
    sections = []
    for slot in profile['voices']:
        cards = []
        for row in records:
            if row['voice'] != slot:
                continue
            player = f'<audio controls preload="none" src="{row["file"]}"></audio>' if row.get('file') else '<p>Audio unavailable</p>'
            cards.append(f'<article><b>{html.escape(row["tone"].title())} · {row["rate"]:.2f}×</b>{player}</article>')
        sections.append(f'<section><h2>{slot.replace("_", " ").title()}</h2>{"".join(cards)}</section>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Tutor speech review</title>
<style>body{font:17px system-ui;max-width:1000px;margin:40px auto;padding:0 24px;background:#f4f5f7;color:#243042}section{background:white;padding:20px;margin:24px 0;border-radius:12px}article{display:inline-flex;vertical-align:top;flex-direction:column;gap:12px;margin:12px;width:280px}audio{width:100%}p{line-height:1.6}</style>
<h1>Tutor speech review</h1><p>Candidate voices — listening review pending. These are generated samples, not participant recordings.</p>
<p>Let's explore this idea together, one step at a time.</p>
<p>Compare voices using Professional / 1.00×. Compare tones within one voice at 1.00×. Compare rates within one voice using Professional. Check pronunciation, speaker consistency, style distinction and comfort. API success does not establish perceptual success.</p>
''' + ''.join(sections) + '''<script>document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>'''
    (OUT / 'index.html').write_text(page)
    print('Saved', sum(r['status'] == 'audio_saved' for r in records), 'of', len(cases), 'samples')

if __name__ == '__main__':
    main()
