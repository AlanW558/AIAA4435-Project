#!/usr/bin/env python3
"""Local researcher controller for the dedicated PICO appearance experiment.

Standard library only. Every device operation targets the explicitly selected
serial; session configuration is built from validated identity, never answers.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import uuid

from launch_session import ROOT, prepare
from session_identity import validate_identity

PACKAGE = 'com.iai.aiaa4435.appearance'
STORAGE = '/sdcard/Android/data/' + PACKAGE + '/files'
CONFIG = STORAGE + '/appearance-session.json'
COMMAND = STORAGE + '/appearance-command.json'
STATUS = STORAGE + '/appearance-status.json'
RESULT = STORAGE + '/appearance-command-result.json'
CAPTURES = STORAGE + '/appearance-captures'
ACTIONS = frozenset(('next', 'resume', 'submit', 'answer', 'undo', 'finish', 'sit'))
DEBUG_ACTIONS = ACTIONS - {'next', 'resume'}
UNDO_VALUES = frozenset(('all', 'jacket_color', 'accessory', 'scale'))
DEMO_UNDO_VALUES = UNDO_VALUES | {'avatar_id', 'outfit'}
CAPABILITY_PROFILES = ('study-v1', 'avatar-demo-v1')


class ControllerError(Exception):
    """Safe operator-facing failure, excluding subprocess output/private data."""


class AdbError(ControllerError):
    def __init__(self, operation, missing=False):
        self.missing = missing
        super().__init__('ADB ' + operation + ' failed; check selected device and USB authorization.')


def strict_json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key.')
            obj[key] = value
        return obj
    def constant(_):
        raise ValueError('Non-finite JSON number.')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def locate_adb(explicit=None):
    chosen = explicit or os.environ.get('APPEARANCE_ADB')
    default = ROOT / 'Builds/AndroidTools/platform-tools/adb.exe'
    if not chosen:
        chosen = str(default) if default.is_file() else shutil.which('adb')
    if not chosen:
        raise ControllerError('ADB not found; provide --adb or APPEARANCE_ADB.')
    resolved = shutil.which(str(chosen))
    if resolved:
        return resolved
    path = Path(chosen).expanduser()
    if not path.is_file():
        raise ControllerError('ADB executable not found; check --adb or APPEARANCE_ADB.')
    return str(path.resolve())


class Adb:
    def __init__(self, executable, serial=None, timeout=15):
        self.executable = str(executable)
        self.serial = serial
        self.timeout = timeout
        self.lock = threading.RLock()

    def run(self, *args, selected=True, timeout=None):
        if selected and (not self.serial or self.serial.startswith('-') or '\x00' in self.serial):
            raise ControllerError('An explicit valid --serial is required for device operations.')
        cmd = [self.executable]
        if selected:
            cmd.extend(['-s', self.serial])
        cmd.extend(str(arg) for arg in args)
        with self.lock:
            try:
                result = subprocess.run(cmd, capture_output=True, check=True,
                                        timeout=timeout or self.timeout)
                return result.stdout
            except subprocess.CalledProcessError as exc:
                missing = b'No such file' in (exc.stderr or b'') or b'No such file' in (exc.output or b'')
                raise AdbError(str(args[0]) if args else 'operation', missing) from None
            except subprocess.TimeoutExpired:
                raise ControllerError('ADB timed out; check the selected device before retrying.') from None
            except OSError:
                raise ControllerError('Could not execute ADB; check the executable path.') from None

    def host_path(self, path):
        """Translate host-side paths only when a Windows ADB runs under WSL."""
        path = Path(path).expanduser().resolve()
        if self.executable.lower().endswith('.exe') and os.name != 'nt':
            try:
                result = subprocess.run(['wslpath', '-w', str(path)], capture_output=True,
                                        check=True, timeout=5)
                translated = result.stdout.decode('utf-8').strip()
                if not translated or '\n' in translated or '\r' in translated:
                    raise ValueError()
                return translated
            except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
                raise ControllerError('Windows ADB requires wslpath -w to translate host paths.') from None
        return str(path)

    def atomic_json(self, destination, data):
        # NamedTemporaryFile is closed before Windows ADB opens it.
        with self.lock:
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as f:
                    name = f.name
                    json.dump(data, f, ensure_ascii=False, allow_nan=False)
                    f.write('\n')
                remote_tmp = destination + '.' + uuid.uuid4().hex + '.tmp'
                self.run('push', self.host_path(name), remote_tmp)
                self.run('shell', 'mv', remote_tmp, destination)
            finally:
                if name:
                    Path(name).unlink(missing_ok=True)


def session_config(data, condition=None, task=None, backend='http://127.0.0.1:8765',
                   build_sha256=None, capability_profile='study-v1'):
    if capability_profile not in CAPABILITY_PROFILES:
        raise ControllerError('Unknown capability profile; choose study-v1 or avatar-demo-v1.')
    try:
        env = prepare(data, condition, task)
    except (ValueError, OSError, KeyError, TypeError):
        raise ControllerError('Invalid session identity, phase, condition/task override, or frozen schedule; verify the session file.') from None
    if capability_profile == 'avatar-demo-v1' and (
            env['APPEARANCE_PHASE'] != 'debug' or task is not None or data.get('task_id')):
        raise ControllerError('Avatar demo requires debug phase without a frozen task.')
    try:
        parsed = urlsplit(backend)
        port = parsed.port
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment or any(c.isspace() for c in backend)):
            raise ValueError()
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, TypeError):
        raise ControllerError('Backend must be an HTTP(S) URL without credentials, query or fragment.') from None
    if build_sha256 is not None and not re.fullmatch(r'[0-9a-fA-F]{64}', build_sha256):
        raise ControllerError('Build SHA-256 must contain exactly 64 hexadecimal characters.')
    formal = env['APPEARANCE_PHASE'] == 'formal'
    config = {
        'schema_version': 'appearance-session-v1',
        'participant_id': env['APPEARANCE_PARTICIPANT_ID'],
        'phase': env['APPEARANCE_PHASE'],
        'study_session_id': env['APPEARANCE_STUDY_SESSION_ID'],
        'assigned': formal,
        'condition': '' if formal else env['APPEARANCE_CONDITION'],
        'task_id': '' if formal else env['APPEARANCE_TASK_ID'],
        'backend_url': backend,
        'capability_profile': capability_profile,
    }
    if build_sha256 is not None:
        config['expected_build_sha256'] = build_sha256.lower()
    return config


def validate_status(data):
    try:
        if not isinstance(data, dict) or data.get('schema_version') != 'appearance-device-status-v1':
            raise ValueError()
        profile = data.get('capability_profile', 'study-v1')
        if profile not in CAPABILITY_PROFILES:
            raise ValueError()
        for key in ('initialized', 'busy', 'validating', 'finished', 'awaiting_block', 'study_complete',
                    'faulted', 'command_accepted', 'can_edit', 'can_finish'):
            if type(data.get(key)) is not bool:
                raise ValueError()
        phase = data.get('phase')
        if phase not in ('debug', 'pilot', 'formal') and (data['initialized'] or phase not in ('', None)):
            raise ValueError()
        if profile == 'avatar-demo-v1' and phase != 'debug':
            raise ValueError()
        if data['initialized']:
            validate_identity(data.get('participant_id'), data.get('phase'), data.get('study_session_id'))
        if not isinstance(data.get('command_id'), str) or not isinstance(data.get('command_error'), str):
            raise ValueError()
    except (ValueError, TypeError):
        raise ControllerError('Device status JSON has an invalid schema, identity or capability profile/phase; no command sent.') from None
    return data


def command_payload(status, action, value=None, text=None, session_id=None):
    validate_status(status)
    if action not in ACTIONS:
        raise ControllerError('Unsupported command action.')
    if not status['initialized'] or status['faulted']:
        raise ControllerError('Device session is not initialized or is faulted; no command sent.')
    if session_id is not None and session_id != status['study_session_id']:
        raise ControllerError('Study session ID differs from fresh device status; no command sent.')
    if action in DEBUG_ACTIONS and status['phase'] != 'debug':
        raise ControllerError('This command is available only in debug sessions.')
    if value is not None and (not isinstance(value, str) or len(value) > 200 or '\x00' in value):
        raise ControllerError('Command value must be a string of at most 200 characters.')
    if text is not None and (not isinstance(text, str) or len(text) > 4000 or '\x00' in text):
        raise ControllerError('Command text must be a string of at most 4000 characters.')
    undo_values = DEMO_UNDO_VALUES if status.get('capability_profile') == 'avatar-demo-v1' and status['phase'] == 'debug' else UNDO_VALUES
    if action == 'undo' and value not in undo_values:
        raise ControllerError('Undo value for this profile must be one of: ' + ', '.join(sorted(undo_values)) + '.')
    if action == 'answer' and not value:
        raise ControllerError('Answer requires the current option ID in --value.')
    if action == 'answer':
        question = status.get('question')
        options = question.get('options', []) if isinstance(question, dict) else []
        if not any(isinstance(option, dict) and option.get('id') == value for option in options):
            raise ControllerError('Answer option is absent from the fresh device question.')
    if action not in ('undo', 'answer') and value is not None:
        raise ControllerError('This action does not accept --value.')
    if action not in ('submit', 'answer') and text is not None:
        raise ControllerError('This action does not accept --text.')
    return {'id': uuid.uuid4().hex, 'study_session_id': status['study_session_id'],
            'action': action, 'value': value, 'text': text}


class Controller:
    def __init__(self, adb):
        self.adb = adb

    def devices(self):
        return self.adb.run('devices', '-l', selected=False).decode('utf-8', errors='replace').strip()

    def install(self, apk):
        path = Path(apk).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != '.apk':
            raise ControllerError('Provide an existing .apk file.')
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        digest = h.hexdigest()
        with self.adb.lock:
            self.adb.run('install', '-r', self.adb.host_path(path), timeout=180)
            self.adb.run('shell', 'mkdir', '-p', STORAGE)
        return {'installed': True, 'package': PACKAGE, 'apk_sha256': digest}

    def configure(self, session_file, **kwargs):
        try:
            data = strict_json(Path(session_file).read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            raise ControllerError('Cannot read a valid session JSON file; configuration was not changed.') from None
        config = session_config(data, **kwargs)
        with self.adb.lock:
            self.adb.run('shell', 'am', 'force-stop', PACKAGE)
            self.adb.run('shell', 'mkdir', '-p', STORAGE)
            self.adb.run('shell', 'rm', '-f', COMMAND, RESULT, STATUS)
            self.adb.atomic_json(CONFIG, config)
        return {'configured': True, 'study_session_id': config['study_session_id'],
                'participant_id': config['participant_id'], 'phase': config['phase'],
                'capability_profile': config['capability_profile'],
                'message': 'Configuration staged; launch the dedicated app to initialize this session.'}

    def launch(self):
        with self.adb.lock:
            output = self.adb.run('shell', 'am', 'start', '-W', '-n', PACKAGE + '/com.unity3d.player.UnityPlayerActivity')
            if b'Error' in output or b'Exception' in output:
                raise ControllerError('Android did not start the dedicated Unity activity; verify the installed APK.')
        return {'launch_requested': True, 'message': 'Launch requested; inspect status for runtime initialization.'}

    def status(self, timeout=None):
        try:
            raw = self.adb.run('exec-out', 'cat', STATUS, timeout=timeout)
        except AdbError as exc:
            if exc.missing:
                return {'state': 'not_ready', 'message': 'Status file absent: configure and launch, then wait for initialization.'}
            raise
        # Some Windows ADB exec-out versions return exit 0 for cat failures.
        # Recognize only the exact diagnostic for this fixed status path.
        missing_status = ('cat: ' + STATUS + ': No such file or directory').encode('utf-8')
        if raw.strip() == missing_status:
            return {'state': 'not_ready', 'message': 'Status file absent: configure and launch, then wait for initialization.'}
        if len(raw) > 1024 * 1024:
            raise ControllerError('Device status exceeds the supported JSON size.')
        try:
            data = validate_status(strict_json(raw.decode('utf-8')))
        except (ValueError, UnicodeError):
            raise ControllerError('Device status is not valid UTF-8 JSON; no command sent.') from None
        return {'state': 'ready' if data['initialized'] else 'starting', 'status': data}

    def command(self, action, value=None, text=None, session_id=None, wait=8):
        if not isinstance(wait, (int, float)) or not 0 <= wait <= 30:
            raise ControllerError('Command acknowledgment wait must be between 0 and 30 seconds.')
        with self.adb.lock:
            current = self.status()
            if 'status' not in current:
                raise ControllerError('Device status is not available; no command sent.')
            payload = command_payload(current['status'], action, value, text, session_id)
            self.adb.atomic_json(COMMAND, payload)
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(.25, remaining))
                try:
                    latest = self.status(timeout=max(.05, deadline - time.monotonic()))
                except ControllerError as exc:
                    return {'command_id': payload['id'], 'acknowledgment': 'unavailable', 'accepted': None,
                            'completion': 'not_confirmed',
                            'message': 'Mailbox written; acknowledgment unavailable. ' + str(exc)}
                status = latest.get('status')
                if status is None:
                    continue  # A writer/startup gap is not an acknowledgment or session switch.
                if status.get('study_session_id') != payload['study_session_id']:
                    raise ControllerError('Device study session changed while awaiting acknowledgment; inspect status before retrying.')
                if status.get('command_id') == payload['id']:
                    accepted = status['command_accepted'] and not status['command_error']
                    return {'command_id': payload['id'], 'acknowledgment': 'accepted' if accepted else 'rejected',
                            'accepted': bool(accepted), 'command_error': status['command_error'],
                            'completion': 'not_confirmed', 'status': status,
                            'message': 'Acknowledgment only; poll status and captures for asynchronous completion.'}
            return {'command_id': payload['id'], 'acknowledgment': 'timeout', 'accepted': None,
                    'completion': 'not_confirmed',
                    'message': 'Mailbox written but acknowledgment timed out; inspect status before retrying.'}

    def collect(self, output):
        path = Path(output).expanduser().resolve()
        base = (ROOT / 'StudyData/pico').resolve()
        if path != base and base not in path.parents:
            raise ControllerError('Collection output must be under repository StudyData/pico.')
        path.mkdir(parents=True, exist_ok=True)
        with self.adb.lock:
            # Read a fresh status before retrieving captures. No questionnaire data is pulled.
            snapshot = self.status()
            self.adb.run('pull', CAPTURES, self.adb.host_path(path), timeout=180)
            (path / 'controller-status.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return {'collected': True, 'output': str(path), 'message': 'Captured runtime files retrieved; inspect contents before study use.'}


def valid_request_origin(host, origin, port):
    """Require an exact loopback authority; no wildcard CORS or DNS rebinding."""
    allowed = {'127.0.0.1:' + str(port), 'localhost:' + str(port)}
    if host not in allowed:
        return False
    return origin == 'http://' + host


PAGE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PICO · 外形实验研究控制台</title><style nonce="__NONCE__">
:root{color-scheme:light;font-family:system-ui,"Microsoft YaHei",sans-serif;color:#18302c;background:#f2f5f1}*{box-sizing:border-box}body{max-width:1120px;margin:auto;padding:36px 24px}header{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:26px}h1{font-size:27px;margin:8px 0}h2{font-size:16px;margin:0 0 18px}p{line-height:1.65}.eyebrow{letter-spacing:3px;font-size:12px;color:#527267}.pill{border:1px solid #b4c9bb;background:#e7efe9;border-radius:30px;padding:9px 16px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.card{background:white;border:1px solid #dce5dd;border-radius:18px;padding:22px;box-shadow:0 4px 20px #1d493006}.wide{grid-column:span 3}.half{grid-column:span 2}.label{font-size:12px;color:#63796f;margin:14px 0 5px}.value{font-size:20px;font-weight:600;overflow-wrap:anywhere}.small{font-size:13px;color:#52685e;white-space:pre-wrap;overflow-wrap:anywhere}.row{display:flex;gap:10px;flex-wrap:wrap}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}button{font:inherit;border:0;border-radius:10px;background:#245f4d;color:white;padding:11px 16px;cursor:pointer}button.secondary{background:#e7eee8;color:#234b3b}button:disabled{opacity:.4;cursor:default}input{width:100%;font:inherit;border:1px solid #c3d3c7;border-radius:10px;padding:12px;margin:10px 0}pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f1;padding:14px;border-radius:10px}#feedback{margin-top:12px;white-space:pre-wrap;color:#694d19}#debug[hidden]{display:none}@media(max-width:760px){.grid{grid-template-columns:1fr}.wide,.half{grid-column:span 1}.metrics{grid-template-columns:1fr}header{display:block}}
</style><header><div><div class="eyebrow">APPEARANCE LAB / RESEARCH ONLY</div><h1>PICO 外形实验控制台</h1><div class="small">研究者专用 · 请勿向参与者展示此页面</div></div><div class="pill" id="connection">正在读取设备…</div></header>
<main class="grid"><section class="card"><h2>设备与关联会话</h2><div class="label">已选择设备</div><div class="small" id="serial"></div><div class="label">参与者 / 阶段</div><div class="value" id="identity">—</div><div class="label">能力配置</div><div class="small" id="profile">—</div><div class="label">研究会话</div><div class="small" id="session">—</div></section>
<section class="card"><h2>实验进度</h2><div class="label">条件</div><div class="value" id="condition">—</div><div class="label">试次 / 分轮 / 轮内</div><div class="value" id="trial">—</div><div class="label">当前任务</div><div class="small" id="task">—</div></section>
<section class="card"><h2>运行状态</h2><div class="value" id="flags">等待状态</div><div class="label">后端 / 当前处理</div><div class="small" id="backend">尚无设备状态</div><div class="label">APK SHA-256</div><div class="small" id="build">—</div></section>
<section class="card wide"><h2>当前实际外形</h2><div class="metrics"><div data-avatar-demo hidden><div class="label">形象</div><div class="value" id="avatar">—</div></div><div data-avatar-demo hidden><div class="label">服装</div><div class="value" id="outfit">—</div></div><div><div class="label" id="colorLabel">外套颜色</div><div class="value" id="color">—</div></div><div><div class="label">配饰</div><div class="value" id="accessory">—</div></div><div><div class="label">比例 / 修订</div><div class="value" id="scale">—</div></div></div></section>
<section class="card wide"><h2>研究者操作</h2><p class="small">试次结束后继续；分轮问卷完成后恢复。操作回执仅代表接受或拒绝，实际完成以设备状态与采集记录为准。</p><div class="row"><button id="next" disabled>下一试次</button><button id="resume" disabled>问卷完成，恢复</button></div><div id="feedback" role="status"></div></section>
<section class="card wide" id="debug" hidden><h2>调试交互 · 仅 DEBUG</h2><div class="label">输入修改请求；留空可提交首个预填任务</div><input id="query" placeholder="输入调试请求" maxlength="4000"><button id="submit">提交请求</button><div class="label" id="question"></div><input id="answerText" placeholder="补充回答（可选）" maxlength="4000"><div class="row" id="options"></div><p class="small">撤销与完成由运行时校验当前状态。</p><div class="row"><button class="secondary" data-undo="all">全部撤销</button><button class="secondary" data-undo="jacket_color">撤销颜色</button><button class="secondary" data-undo="accessory">撤销配饰</button><button class="secondary" data-undo="scale">撤销比例</button><button class="secondary" data-undo="avatar_id" data-avatar-demo hidden>撤销形象</button><button class="secondary" data-undo="outfit" data-avatar-demo hidden>撤销服装</button><button class="secondary" id="sit">坐下</button><button id="finish">完成当前任务</button></div></section>
<section class="card wide"><h2>初始化与证据</h2><p class="small">在项目根目录执行以下命令。先使用真实的研究者会话元数据配置，再启动并检查状态。正式阶段的条件与任务来自冻结分配表。</p><pre id="instructions"></pre><p class="small">此控制台不会读取或发送问卷回答。连接失败时不会生成演示状态。设备内的实际采集文件位于 appearance-captures。</p></section></main>
<script nonce="__NONCE__">'use strict';
const token=__TOKEN__, serial=__SERIAL__;
let current=null, pending=false;
const el=id=>document.getElementById(id), show=(id,value)=>{el(id).textContent=value===undefined||value===null||value===''?'—':String(value)};
show('serial',serial);show('instructions',__INSTRUCTIONS__);
function clear(){current=null;for(const id of ['identity','profile','session','condition','trial','task','build','avatar','outfit','color','accessory','scale'])show(id,'—');for(const node of document.querySelectorAll('[data-avatar-demo]'))node.hidden=true;show('colorLabel','外套颜色');el('debug').hidden=true;el('next').disabled=true;el('resume').disabled=true;el('options').replaceChildren();}
function paint(data){const s=data.status;if(!s){clear();show('connection',data.state==='not_ready'?'等待启动':'设备不可用');show('flags','尚未初始化');show('backend',data.message);return}current=s;const profile=s.capability_profile??'study-v1',demo=profile==='avatar-demo-v1'&&s.phase==='debug';show('profile',profile);for(const node of document.querySelectorAll('[data-avatar-demo]'))node.hidden=!demo;show('connection',data.state==='ready'?'设备已连接':'设备启动中');show('identity',s.participant_id+' / '+s.phase);show('session',s.study_session_id);show('condition',s.condition);show('trial',[s.trial,s.block,s.within_block].map(x=>x??'—').join(' / '));show('task',s.task_id);show('build',s.build_sha256);show('flags',s.faulted?'运行异常':s.study_complete?'研究会话已结束':s.awaiting_block?'暂停 · 等待分轮问卷':s.validating?'正在核验':s.busy?'处理中':s.finished?'当前任务已完成':s.initialized?'就绪':'初始化中');show('backend',[s.decision,s.message,s.realtime===undefined?'':JSON.stringify(s.realtime)].filter(Boolean).join('\n'));const o=s.observed||{};show('avatar',o.avatar_id);show('outfit',o.outfit);show('colorLabel',demo&&o.avatar_id==='nailong'?'主体颜色':'服装颜色');show('color',o.jacket_color);show('accessory',o.accessory);show('scale',(o.scale??'—')+' / '+(o.revision??'—'));el('next').disabled=pending||!s.initialized||s.faulted||!s.finished||s.awaiting_block||s.study_complete;el('resume').disabled=pending||!s.initialized||s.faulted||!s.awaiting_block||s.study_complete;el('debug').hidden=s.phase!=='debug';show('question',s.question?.text);el('options').replaceChildren();for(const option of s.question?.options||[]){const b=document.createElement('button');b.textContent=option.label;b.disabled=pending||s.busy||s.validating;b.addEventListener('click',()=>send('answer',option.id,el('answerText').value));el('options').appendChild(b)}for(const b of el('debug').querySelectorAll('button'))b.disabled=pending||!s.initialized||s.faulted||s.busy||s.validating;el('finish').disabled=pending||!s.can_finish||s.busy||s.validating;}
async function poll(){try{const r=await fetch('/api/status',{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'读取失败');paint(d)}catch(e){clear();show('connection','设备连接失败');show('flags','无法读取实际状态');show('backend',e.message)}}
async function send(action,value=null,text=null){if(!current||pending)return;pending=true;const sid=current.study_session_id;paint({state:'ready',status:current});show('feedback','等待设备回执…');try{const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Appearance-Token':token},body:JSON.stringify({action,value,text,session_id:sid})});const d=await r.json();if(!r.ok&&!d.acknowledgment)throw Error(d.error||'操作失败');const labels={accepted:'设备已接受；等待实际处理完成',rejected:'设备已拒绝',timeout:'回执超时；请检查状态后再操作',unavailable:'回执不可用；请检查状态后再操作'};show('feedback',(labels[d.acknowledgment]||d.acknowledgment)+(d.command_error?' · '+d.command_error:''))}catch(e){show('feedback',e.message)}finally{pending=false;await poll()}}
el('next').onclick=()=>send('next');el('resume').onclick=()=>send('resume');el('submit').onclick=()=>send('submit',null,el('query').value);el('finish').onclick=()=>send('finish');el('sit').onclick=()=>send('sit');for(const b of document.querySelectorAll('[data-undo]'))b.onclick=()=>send('undo',b.dataset.undo);
async function loop(){if(!pending)await poll();setTimeout(loop,750)}loop();
</script></html>'''


def make_handler(controller, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Query/command text is never logged by the HTTP server.

        def reply(self, code, data, kind='application/json; charset=utf-8', nonce=None):
            raw = data.encode('utf-8') if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            policy = "default-src 'none'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            if nonce:
                policy += "; script-src 'nonce-" + nonce + "'; style-src 'nonce-" + nonce + "'"
            self.send_header('Content-Security-Policy', policy)
            self.end_headers()
            self.wfile.write(raw)

        def host_valid(self):
            port = self.server.server_port
            return self.headers.get('Host') in {'127.0.0.1:' + str(port), 'localhost:' + str(port)}

        def do_GET(self):
            if not self.host_valid():
                self.reply(403, {'error': 'Loopback Host required.'})
                return
            if self.path == '/':
                nonce = secrets.token_hex(16)
                # Serial is untrusted host input; escape script metacharacters too.
                def js(value):
                    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
                instructions = ('python3 Tools/AppearanceExperiment/pico.py --serial ' + shlex.quote(controller.adb.serial)
                                + ' configure --session-file /path/to/session.json\n'
                                + 'python3 Tools/AppearanceExperiment/pico.py --serial ' + shlex.quote(controller.adb.serial) + ' launch\n'
                                + 'python3 Tools/AppearanceExperiment/pico.py --serial ' + shlex.quote(controller.adb.serial)
                                + ' collect --output StudyData/pico/session-capture')
                page = PAGE.replace('__NONCE__', nonce).replace('__TOKEN__', js(token)).replace('__SERIAL__', js(controller.adb.serial)).replace('__INSTRUCTIONS__', js(instructions))
                self.reply(200, page, 'text/html; charset=utf-8', nonce)
            elif self.path == '/api/status':
                try:
                    self.reply(200, controller.status())
                except ControllerError as exc:
                    self.reply(503, {'state': 'unavailable', 'error': str(exc)})
            else:
                self.reply(404, {'error': 'Not found.'})

        def do_POST(self):
            if (not valid_request_origin(self.headers.get('Host'), self.headers.get('Origin'), self.server.server_port)
                    or not secrets.compare_digest(self.headers.get('X-Appearance-Token', ''), token)):
                self.reply(403, {'error': 'Loopback origin and researcher page token required.'})
                return
            if self.path != '/api/command':
                self.reply(404, {'error': 'Not found.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                self.reply(415, {'error': 'application/json required.'})
                return
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError()
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 32768:
                    raise ValueError()
                body = strict_json(self.rfile.read(size).decode('utf-8'))
                if not isinstance(body, dict) or set(body) - {'action', 'value', 'text', 'session_id'}:
                    raise ValueError()
                if not isinstance(body.get('action'), str) or not isinstance(body.get('session_id'), str):
                    raise ValueError()
            except (ValueError, UnicodeError):
                self.reply(400, {'error': 'Invalid command JSON or body size.'})
                return
            try:
                result = controller.command(body['action'], body.get('value'), body.get('text'), body['session_id'])
                self.reply(409 if result['acknowledgment'] == 'rejected' else 200, result)
            except ControllerError as exc:
                self.reply(400, {'error': str(exc)})
    return Handler


def serve(controller, port=8766):
    token = secrets.token_hex(32)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(controller, token))
    except OSError:
        raise ControllerError('Could not bind the loopback controller port; choose an unused --port.') from None
    print('研究者控制台：http://127.0.0.1:' + str(server.server_port), flush=True)
    with contextlib.closing(server):
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', help='ADB executable; otherwise APPEARANCE_ADB, bundled Windows ADB, or PATH adb.')
    parser.add_argument('--serial', help='Explicit device serial (required except devices).')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('devices', help='List devices without choosing one implicitly.')
    install = sub.add_parser('install', help='Install with -r and report local APK SHA-256; preserve app data.')
    install.add_argument('--apk', type=Path, required=True)
    config = sub.add_parser('configure', help='Validate identity, stop the app and atomically stage metadata.')
    config.add_argument('--session-file', type=Path, required=True)
    config.add_argument('--condition', choices=('E', 'A', 'N', 'S'))
    config.add_argument('--task')
    config.add_argument('--backend', default='http://127.0.0.1:8765')
    config.add_argument('--build-sha256')
    config.add_argument('--capability-profile', choices=CAPABILITY_PROFILES, default='study-v1',
                        help='Appearance contract; avatar-demo-v1 requires debug without a frozen task.')
    sub.add_parser('launch')
    sub.add_parser('status')
    command = sub.add_parser('command', help='Send a guarded mailbox command; acknowledgment is not completion.')
    command.add_argument('action', choices=sorted(ACTIONS))
    command.add_argument('--value')
    command.add_argument('--text')
    command.add_argument('--session-id', help='Must match fresh device status; inferred if omitted.')
    command.add_argument('--wait', type=float, default=8, help='Acknowledgment wait, 0–30 seconds (default 8).')
    collect = sub.add_parser('collect')
    collect.add_argument('--output', type=Path, required=True)
    web = sub.add_parser('serve')
    web.add_argument('--port', type=int, default=8766)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.operation != 'devices' and not args.serial:
        parser.error('An explicit --serial is required; use devices to list candidates.')
    try:
        controller = Controller(Adb(locate_adb(args.adb), args.serial))
        if args.operation == 'devices':
            print(controller.devices())
            return 0
        if args.operation == 'install':
            result = controller.install(args.apk)
        elif args.operation == 'configure':
            result = controller.configure(args.session_file, condition=args.condition, task=args.task,
                                          backend=args.backend, build_sha256=args.build_sha256,
                                          capability_profile=args.capability_profile)
        elif args.operation == 'launch':
            result = controller.launch()
        elif args.operation == 'status':
            result = controller.status()
        elif args.operation == 'command':
            result = controller.command(args.action, args.value, args.text, args.session_id, args.wait)
        elif args.operation == 'collect':
            result = controller.collect(args.output)
        else:
            if not 0 <= args.port <= 65535:
                raise ControllerError('Port must be between 0 and 65535.')
            serve(controller, args.port)
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.operation == 'command' and result['acknowledgment'] != 'accepted':
            return 2 if result['acknowledgment'] == 'rejected' else 3
        if args.operation == 'status' and result['state'] != 'ready':
            return 3
        return 0
    except ControllerError as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 1
    except OSError:
        print('Error: Could not read or write a local file; check paths and permissions.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
