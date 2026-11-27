#!/usr/bin/env python3
"""Build an offline listening/questionnaire page from published auxiliary results.

No provider calls, no automatic ratings, and no access to unreleased results.
Listening evidence retains its original task releases. Feedback is collected
once per attribute, without importing or averaging earlier task ratings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, unquote
import uuid

from attribute_feedback import VERSION, LEGACY_VERSION, SUPPORTED_VERSIONS, build_attributes, feedback_items

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / 'StudyData/text-check-v3'
CONDITIONS = ('E', 'A', 'N', 'S')
NAMES = {'E': 'Execute-first', 'A': 'Always-ask', 'N': 'Native-gate', 'S': 'Selective'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def inside(root, relative):
    candidate = Path(relative)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError('Result/audio paths must stay inside the auxiliary directory.')
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Result/audio symlink leaves the auxiliary directory.')
    return resolved


def checkpoint(path, code):
    envelope = json.loads(path.read_text())
    record = envelope['payload']
    if envelope.get('sha256') != digest(canonical(record)) or record.get('task_code') != code:
        raise ValueError(f'{code}: invalid checkpoint checksum or identity.')
    return record


def release_identity(branches):
    return digest(canonical({c: {'branch_revision': branches[c]['branch_revision'],
                                'result': branches[c]['result']} for c in CONDITIONS}))


def current_branches(record):
    result = {}
    for c, b in record['runtime']['task']['_branches'].items():
        projection = {'branch_id': b['branch_id'], 'branch_revision': b['revision'],
                      'status': b['status'], 'outcome': b['outcome'], 'message': b['message'], 'state': b['state']}
        result[c] = {'branch_revision': b['revision'], 'result': projection}
    return result


def clarification_details(release, record, condition):
    explicit = release.get('clarifications', {}).get(condition)
    if explicit is not None:
        occurred, count, turns = explicit.get('occurred'), explicit.get('count'), explicit.get('turns')
        if type(occurred) is not bool or type(count) is not int or not isinstance(turns, list):
            raise ValueError('Invalid clarification annotation.')
        if count != len(turns) or occurred != bool(turns):
            raise ValueError('Clarification count and occurrence disagree.')
        for turn in turns:
            if not isinstance(turn, dict) or not isinstance(turn.get('question'), str):
                raise ValueError('A clarification needs its actual question text.')
        return {'status': 'yes' if occurred else 'no', 'count': count, 'turns': turns}
    # Older checkpoints may retain answers in the latest runtime round. Earlier
    # rounds can have been cleared, so absent evidence is never labelled "No".
    questions = {}
    for branch in record.get('runtime', {}).get('task', {}).get('_branches', {}).values():
        for answer in branch.get('answers', []):
            questions[answer.get('question_id')] = answer.get('question', {}).get('text')
    turns = []
    for operation in record.get('operations', []):
        if operation.get('operation') != 'answer' or operation.get('condition') != condition:
            continue
        body = operation['body']
        qid = body['question_id']
        answer = record.get('answers', {}).get(qid, {})
        question = answer.get('question') or operation.get('question') or questions.get(qid)
        if isinstance(question, dict):
            question = question.get('text')
        turns.append({'question_id': qid, 'question': question or 'Question text not retained in this older record.',
                      'answer': body.get('response', {}).get('text', ''),
                      'source': answer.get('input_source') or operation.get('input_source') or 'not_recorded'})
    return {'status': 'yes' if turns else 'unknown', 'count': len(turns), 'turns': turns,
            'evidence_note': 'Older record: annotation may not contain all earlier rounds.'}


def audio_material(entry, directory, runtime_id, label):
    """Read only a published, runtime-bound, checksummed comparison asset."""
    if (not isinstance(entry, dict) or entry.get('runtime_id') != runtime_id
            or not all(isinstance(entry.get(key), str) for key in ('file', 'sha256', 'text'))):
        raise ValueError(f'{label}: audio identity or metadata mismatch.')
    wav = inside(directory, entry['file'])
    if digest(wav.read_bytes()) != entry['sha256']:
        raise ValueError(f'{label}: audio checksum mismatch.')
    return {'audio_url': quote(wav.relative_to(directory).as_posix()),
            'text': entry['text'], 'purpose': entry.get('purpose')}


def result_details(result, baseline):
    """Describe recorded state changes, without judging task success."""
    settings = result.get('state', {}).get('settings')
    starting = baseline.get('settings') if isinstance(baseline, dict) else None
    comparable = isinstance(settings, dict) and isinstance(starting, dict)
    return {'status': result.get('status'), 'outcome': result.get('outcome'),
            'message': result.get('message'), 'settings': settings if isinstance(settings, dict) else None,
            'baseline_settings': starting if isinstance(starting, dict) else None,
            'comparison_available': comparable,
            'setting_changes': [{'field': key, 'before': starting.get(key), 'after': settings.get(key)}
                                for key in sorted(set(starting) | set(settings))
                                if starting.get(key) != settings.get(key)] if comparable else []}


def validate_generated_reply(entry, release, condition):
    """New runs must play the actual latest reply from the frozen branch.

    Legacy releases can retain their original samples, but cannot masquerade as
    generated-reply releases merely because their WAV checksum still matches.
    """
    label = f"{release['task_code']}/{condition}"
    view = release['view']; branch = view['branches'][condition]
    baseline = view.get('baseline', {}).get('conversation')
    conversation = branch['result'].get('state', {}).get('conversation')
    if not isinstance(baseline, list) or not isinstance(conversation, list):
        raise ValueError(f'{label}: generated reply requires its baseline and recorded conversation.')
    previous = {exchange['id'] for exchange in baseline}
    actual = [exchange for exchange in conversation if exchange['id'] not in previous]
    if not actual:
        raise ValueError(f'{label}: generated reply must come from a new conversation exchange.')
    exchange = actual[-1]
    text = '\n'.join(message['content'] for message in exchange['messages'] if message['role'] == 'assistant')
    reveal_id = (view.get('latest_reveal') or {}).get('reveal_id')
    if (entry.get('purpose') != 'reply' or type(entry.get('branch_revision')) is not int
            or entry['branch_revision'] != branch['branch_revision']
            or type(entry.get('exchange_id')) is not int or entry['exchange_id'] != exchange['id']
            or not text.strip() or entry.get('text') != text
            or not isinstance(exchange.get('settings'), dict) or entry.get('settings') != exchange['settings']
            or not reveal_id or entry.get('latest_reveal_id') != reveal_id):
        raise ValueError(f'{label}: generated reply audio does not match its recorded branch, exchange, text, settings or reveal.')


def collect(directory, questionnaire_version=VERSION):
    if questionnaire_version not in SUPPORTED_VERSIONS:
        raise ValueError('Unsupported attribute questionnaire version.')
    directory = Path(directory).resolve()
    metadata = json.loads((directory / 'batch.json').read_text())
    catalog_path = inside(directory, 'catalog.json') if (directory / 'catalog.json').exists() else ROOT / 'Assets/Project/Resources/Tutor/StudyTaskSequence.json'
    catalog_bytes = catalog_path.read_bytes()
    if metadata.get('catalog_sha256') != digest(catalog_bytes):
        raise ValueError('Task catalog no longer matches this batch.')
    catalog = json.loads(catalog_bytes)
    questionnaire = json.loads((ROOT / 'Assets/Project/Resources/Tutor/StudyQuestionnaires.json').read_text())
    if questionnaire['attribute_version'] not in ('attribute-feedback-v3', *SUPPORTED_VERSIONS):
        raise ValueError('Unsupported questionnaire version.')
    items = [item for item in questionnaire['items'] if item['id'] in ('A0', 'A1', 'A2', 'A3', 'A4')]
    if [item['id'] for item in items] != ['A0', 'A1', 'A2', 'A3', 'A4']:
        raise ValueError('Expected the five registered attribute questionnaire items.')
    tasks = []
    for module in catalog['modules']:
        for spec in module['tasks']:
            code = spec['task_code']
            display_code = spec.get('display_code', code)
            if not isinstance(display_code, str) or not display_code.strip():
                raise ValueError(f'{code}: invalid participant-visible task code.')
            task = {'task_code': code, 'display_code': display_code, 'domain': module['direction'], 'title': module['title'],
                    'scenario': spec['scenario'], 'goal': spec['instructions'], 'context': spec['context_text'],
                    'keep_unchanged': spec.get('keep_unchanged', 'All settings not targeted by this task.'),
                    'request_example': spec.get('request_example', ''),
                    'status': 'pending', 'status_text': 'No published result yet.'}
            path = directory / 'tasks' / code / 'checkpoint.json'
            if not path.exists():
                tasks.append(task)
                continue
            record = checkpoint(path, code)
            published = record.get('published_release')
            if record.get('pending') or record['runtime'].get('processing'):
                task['status_text'] = 'Processing or interrupted. Results remain hidden.'
            elif not record['runtime']['task'].get('_latest_reveal'):
                task['status_text'] = 'Waiting for all strategy results and required clarification.'
            elif published:
                release = json.loads((inside(directory, published['directory']) / 'result.json').read_text())
                if release.get('task_code') != code or release.get('batch_id') != metadata['batch_id']:
                    raise ValueError(f'{code}: published result identity mismatch.')
                if release.get('questionnaire_version') not in ('attribute-feedback-v3', *SUPPORTED_VERSIONS):
                    raise ValueError(f'{code}: questionnaire version mismatch.')
                generated = metadata.get('response_mode') == 'generated_reply' or release.get('response_mode') == 'generated_reply'
                if generated:
                    if (release.get('response_mode') != 'generated_reply' or release.get('collection_unit') != 'attribute'
                            or release['questionnaire_version'] not in SUPPORTED_VERSIONS):
                        raise ValueError(f'{code}: generated-reply release must retain its attribute-summary contract.')
                    if release.get('baseline_audio') or release.get('listening_materials'):
                        raise ValueError(f'{code}: generated-reply releases cannot include fixed baseline or reference audio.')
                rid = release['release_id']
                if not release.get('view', {}).get('results_visible') or rid != published.get('release_id'):
                    raise ValueError(f'{code}: invalid publication evidence.')
                if rid != release_identity(release['view']['branches']):
                    raise ValueError(f'{code}: published branch checksum mismatch.')
                if rid != release_identity(current_branches(record)):
                    task['status_text'] = 'Results changed after publication. Await an updated release.'
                else:
                    cards = {}
                    if set(release['audio']) != set(CONDITIONS):
                        raise ValueError(f'{code}: all four strategy audio entries are required.')
                    for condition in CONDITIONS:
                        entry = release['audio'][condition]
                        branch_result = release['view']['branches'][condition]['result']
                        actual_result = result_details(branch_result, release['view'].get('baseline'))
                        if entry is None:
                            failure = release.get('technical_failures', {}).get(condition)
                            if (branch_result.get('status') != 'stopped' or not isinstance(failure, dict)
                                    or not isinstance(failure.get('error_code'), str) or not failure['error_code']):
                                raise ValueError(f'{code}/{condition}: missing audio requires a stopped branch and explicit technical-failure evidence.')
                            cards[condition] = {'name': NAMES[condition], 'audio_url': None, 'text': '', 'purpose': 'unavailable',
                                                'technical_failure': {'error_code': failure['error_code']},
                                                'clarification': clarification_details(release, record, condition),
                                                'result': actual_result}
                            continue
                        if entry.get('condition') != condition or entry.get('runtime_id') != record['runtime_id']:
                            raise ValueError(f'{code}/{condition}: audio identity mismatch.')
                        if generated: validate_generated_reply(entry, release, condition)
                        wav = inside(directory, entry['file'])
                        if digest(wav.read_bytes()) != entry['sha256']:
                            raise ValueError(f'{code}/{condition}: audio checksum mismatch.')
                        cards[condition] = {'name': NAMES[condition], 'audio_url': quote(wav.relative_to(directory).as_posix()),
                                            'text': entry['text'], 'purpose': entry.get('purpose'),
                                            'clarification': clarification_details(release, record, condition),
                                            'result': actual_result}
                    task.update(status='published', status_text='Published', release_id=rid,
                                request=release['request'], conditions=cards,
                                questionnaire_version=release['questionnaire_version'])
                    followups = release.get('followup_questions', [])
                    if not isinstance(followups, list) or any(not isinstance(q, dict)
                            or not isinstance(q.get('text'), str) or not q['text'].strip()
                            or not isinstance(q.get('source'), str)
                            or q.get('condition') not in (*CONDITIONS, None) for q in followups):
                        raise ValueError(f'{code}: invalid follow-up question evidence.')
                    task['followup_questions'] = followups
                    baseline = release.get('baseline_audio')
                    task['baseline_audio'] = (audio_material(baseline, directory, record['runtime_id'], f'{code}/baseline')
                                              if baseline is not None else None)
                    materials = release.get('listening_materials', [])
                    if not isinstance(materials, list):
                        raise ValueError(f'{code}: invalid listening material list.')
                    task['listening_materials'] = []
                    for material in materials:
                        if (not isinstance(material, dict) or not isinstance(material.get('label'), str)
                                or not material['label'].strip()):
                            raise ValueError(f'{code}: a listening material requires its supplied label.')
                        task['listening_materials'].append({'label': material['label'],
                            'audio': audio_material(material.get('audio'), directory, record['runtime_id'], f'{code}/reference')})
            tasks.append(task)
    if len({task['display_code'] for task in tasks}) != len(tasks):
        raise ValueError('Participant-visible task codes must be unique.')
    cards = [card for task in tasks if task['status'] == 'published' for card in task['conditions'].values()]
    source_versions = sorted({t['questionnaire_version'] for t in tasks if t['status'] == 'published'})
    return {'schema': 'tutor-text-listening-review-v1', 'batch_id': metadata['batch_id'],
            'generated_at': datetime.now(timezone.utc).isoformat(), 'questionnaire_version': questionnaire_version,
            'source_questionnaire_version': source_versions[0] if len(source_versions) == 1 else questionnaire_version,
            'source_questionnaire_versions': source_versions,
            'items': feedback_items(items, questionnaire_version), 'tasks': tasks, 'attributes': build_attributes(tasks),
            'audio_count': sum(bool(card['audio_url']) for card in cards),
            'baseline_audio_count': sum(bool(task.get('baseline_audio')) for task in tasks),
            'listening_material_count': sum(len(task.get('listening_materials', [])) for task in tasks),
            'technical_failure_count': sum(bool(card.get('technical_failure')) for card in cards)}


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tutor audio review and feedback</title>
<style>
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#193b35;background:#eef2ef;font-size:16px;line-height:1.55;accent-color:#246b5f}
*{box-sizing:border-box}body{margin:0}button,textarea,input{font:inherit}button{cursor:pointer;border:1px solid #abc4bc;background:#fff;color:#193b35;border-radius:9px;padding:.55rem .8rem}button:hover{background:#e4efea}button:disabled{cursor:not-allowed;opacity:.5}button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #c17c3d;outline-offset:2px}header{background:#173d36;color:#f3f7f3;padding:1.15rem 1.6rem}h1{font-size:1.45rem;margin:0 0 .35rem}header p{max-width:1150px;font-size:.91rem;margin:.35rem 0;color:#dbe9e2}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);min-height:75vh}aside{padding:1.1rem;background:#e1eae4;border-right:1px solid #c4d6cb;position:sticky;top:0;height:100vh;overflow:auto}aside h2{font-size:.93rem;margin:1rem 0 .45rem}nav .group{display:grid;grid-template-columns:1fr 1fr;gap:.35rem}nav button{font-size:.83rem;padding:.5rem .3rem}nav button.active{background:#1d5e51;color:#fff;border-color:#1d5e51}nav button.pending{color:#65736d}nav .done{font-size:.7rem;display:block}main{padding:1.3rem;max-width:1500px;width:100%;margin:auto}main h2{margin:.15rem 0;font-size:1.45rem}p{margin:.55rem 0}.task-intro,.card,.empty,.toolbar{background:#fff;border:1px solid #cbdad2;border-radius:13px;padding:1.1rem;margin-bottom:1rem}.task-intro .label{font-size:.8rem;color:#527268;text-transform:uppercase;letter-spacing:.05em}blockquote{margin:.5rem 0;padding:.7rem .9rem;border-left:3px solid #87b5a5;background:#f1f6f2;white-space:pre-wrap}details{margin:.6rem 0}summary{cursor:pointer;color:#315f51}pre,.pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;align-items:start}.card{margin:0;padding:1.1rem}.card h3{margin:0 0 .7rem;font-size:1.12rem}.audio-block{padding:.8rem;background:#f0f5f1;border-radius:10px;border:1px solid #d6e4dc}audio{display:block;width:100%;margin:.4rem 0 .6rem}.clarify{padding:.7rem;background:#fff;border-radius:8px;border:1px solid #d6e4dc;font-size:.92rem}.clarify h4{margin:0 .2rem .5rem 0;font-size:1rem}.clarify article{border-top:1px solid #dbe6df;margin-top:.65rem;padding-top:.4rem}.clarify .source{font-size:.8rem;color:#596d63}.muted{font-size:.86rem;color:#5b7066}.notice{border-left:4px solid #ad7c45;padding:.55rem .75rem;background:#fff5e4}.questionnaire{margin-top:1.2rem}fieldset{padding:0;margin:1.05rem 0;border:0;min-width:0}legend{font-weight:600;font-size:1rem;margin-bottom:.5rem;width:100%}.help{font-size:.85rem;color:#5b7066;margin:.2rem 0 .5rem}.choices{display:flex;gap:.35rem;flex-wrap:wrap}.choice{display:inline-flex;gap:.35rem;align-items:center;padding:.5rem .65rem;border:1px solid #bdcfc4;border-radius:8px;font-size:.9rem;cursor:pointer;min-height:42px}.choice:has(input:checked){background:#dbece1;border-color:#34765e}.choice input{margin:0}.numeric .choice{flex:1;justify-content:center;min-width:38px;padding:.45rem .25rem}.scale{display:flex;justify-content:space-between;font-size:.8rem;color:#536d60;gap:1rem;margin-top:.3rem}.special{margin-top:.45rem}.comment-label{display:block;font-weight:600;font-size:.95rem;margin-top:1rem}textarea{width:100%;min-height:72px;resize:vertical;border:1px solid #bdcfc4;border-radius:8px;padding:.55rem;margin-top:.35rem}.toolbar{margin-top:1rem;display:flex;align-items:center;gap:.8rem;flex-wrap:wrap}.primary{background:#235f50;color:white;border-color:#235f50}.primary:hover{background:#184b3d}.status{font-size:.88rem}.topbuttons{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.7rem}#message{padding:.7rem 0}.small{font-size:.8rem}.pending-label{font-size:.7rem;opacity:.8}a{color:#1a654e} @media(max-width:1050px){.grid{grid-template-columns:1fr}.layout{grid-template-columns:210px minmax(0,1fr)}}@media(max-width:650px){.layout{display:block}aside{position:static;height:auto;border-right:0}nav{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}nav h2{margin-top:0}main{padding:.7rem}header{padding:1rem}.grid{gap:.7rem}.card{padding:.8rem}}
.recorded-result{border-left:3px solid #87b5a5;padding:.3rem .7rem;margin-bottom:.85rem}.settings-table{width:100%;border-collapse:collapse;font-size:.82rem;table-layout:fixed}.settings-table th,.settings-table td{border-bottom:1px solid #d6e4dc;padding:.4rem .25rem;text-align:left;overflow-wrap:anywhere}.listening-materials h3{margin-top:0}.reference-material{margin-top:.9rem}.reference-material h4{margin:.2rem 0}.attribute-nav{width:100%;margin-top:.5rem;font-weight:600}.listen-links{display:flex;gap:.45rem;flex-wrap:wrap;margin:.7rem 0}.attribute-scope{border-left:4px solid #34765e;background:#edf5ef;padding:.65rem .85rem}.preference-card{margin-top:1rem}.source-details{font-size:.8rem;color:#5b7066}.questionnaire-card .questionnaire{margin-top:0}
</style></head><body>
<header><h1>Tutor audio review and feedback</h1><p>Four attributes · Four strategies · One questionnaire per attribute</p>
<p>每个属性听完 8 个任务后统一填写：4 个策略各 5 题，加 1 项策略偏好，共 21 项。任务页只用于试听，不逐题评分。</p><p>辅助效果检查：本轮澄清回复由助手按你的授权代拟。请结合问题、回复和音频评价；评分由你填写，不会自动生成。These records are auxiliary engineering checks, not formal participant submissions.</p></header>
<div class="layout"><aside><p id="coverage" class="small"></p><nav id="navigation" aria-label="Tasks and attribute questionnaires"></nav></aside>
<main><div class="topbuttons"><button id="exportAll">Download all drafts (backup)</button><button id="exportComplete">Download completed attributes</button></div><div id="message" role="status" aria-live="polite"></div><div id="task"></div></main></div>
<script id="report-data" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA=JSON.parse(document.getElementById('report-data').textContent);
const CONDITIONS=['E','A','N','S'];
const IDS=['A0','A1','A2','A3','A4'];
const NAMES={E:'Execute-first',A:'Always-ask',N:'Native-gate',S:'Selective'};
const MULTI_PREFERENCE=DATA.questionnaire_version==='attribute-summary-feedback-v3';
const published=DATA.tasks.filter(t=>t.status==='published');
const publishedAttributes=DATA.attributes.filter(g=>g.status==='published');
let active={kind:'task',id:(published[0]||DATA.tasks[0]).task_code};
const drafts=new Map();let storageAvailable=true;
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined&&text!==null)e.textContent=text;if(cls)e.className=cls;return e;}
function taskLabel(task){const t=typeof task==='string'?DATA.tasks.find(t=>t.task_code===task):task;return t.display_code||t.task_code;}
function objectKeys(value,expected){return Boolean(value)&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===expected.length&&expected.every(k=>Object.hasOwn(value,k));}
function key(g){const base=`tutor-text-attribute-feedback-v1:${DATA.batch_id}:${g.domain}:${g.release_set_id}`;return DATA.questionnaire_version==='attribute-summary-feedback-v1'?base:`${base}:${DATA.questionnaire_version}`;}
function blank(g){return {schema:'tutor-text-attribute-feedback-v1',questionnaire_version:DATA.questionnaire_version,collection_unit:'attribute',batch_id:DATA.batch_id,domain:g.domain,task_releases:{...g.task_releases},conditions:Object.fromEntries(CONDITIONS.map(c=>[c,{answers:Object.fromEntries(IDS.map(id=>[id,{status:'unanswered',value:null}])),extras:{reasons:[],comment:'',comment_confirmed:false}}])),preference:{status:'unanswered',value:null}};}
function answerValid(id,a,final=false){if(!objectKeys(a,['status','value']))return false;if(a.status==='unable_to_judge')return a.value===null;if(a.status==='unanswered')return !final&&a.value===null;if(a.status!=='answered')return false;return DATA.items.find(item=>item.id===id)?.scale==='category'?['fully_met','partly_met','not_met'].includes(a.value):Number.isInteger(a.value)&&a.value>=1&&a.value<=7;}
function preferenceValid(a,final=false){
  if(!objectKeys(a,['status','value']))return false;
  if(a.status==='unanswered')return !final&&a.value===null;
  if(!MULTI_PREFERENCE){if(a.status==='unable_to_judge')return a.value===null;return a.status==='answered'&&[...CONDITIONS,'no_preference'].includes(a.value);}
  if(a.status!=='answered'||!Array.isArray(a.value))return false;
  return a.value.length===1&&a.value[0]==='no_preference'||a.value.length>=1&&a.value.length<=4&&new Set(a.value).size===a.value.length&&a.value.every(c=>CONDITIONS.includes(c));
}
function nextPreference(saved,value,checked){
  if(!MULTI_PREFERENCE)return value===null?{status:'unable_to_judge',value:null}:{status:'answered',value};
  let values=saved.status==='answered'&&Array.isArray(saved.value)?saved.value.filter(c=>CONDITIONS.includes(c)):[];
  if(value==='no_preference')values=checked?['no_preference']:[];
  else values=CONDITIONS.filter(c=>c===value?checked:values.includes(c));
  return values.length?{status:'answered',value:values}:{status:'unanswered',value:null};
}
function draftValid(g,d){
  if(!objectKeys(d,['schema','questionnaire_version','collection_unit','batch_id','domain','task_releases','conditions','preference'])||d.schema!=='tutor-text-attribute-feedback-v1'||d.questionnaire_version!==DATA.questionnaire_version||d.collection_unit!=='attribute'||d.batch_id!==DATA.batch_id||d.domain!==g.domain)return false;
  if(!objectKeys(d.task_releases,Object.keys(g.task_releases))||!Object.entries(g.task_releases).every(([code,rid])=>d.task_releases[code]===rid)||!objectKeys(d.conditions,CONDITIONS)||!preferenceValid(d.preference))return false;
  return CONDITIONS.every(c=>{const section=d.conditions[c];if(!objectKeys(section,['answers','extras'])||!objectKeys(section.answers,IDS)||!IDS.every(id=>answerValid(id,section.answers[id])))return false;const e=section.extras;return objectKeys(e,['reasons','comment','comment_confirmed'])&&Array.isArray(e.reasons)&&e.reasons.length===0&&typeof e.comment==='string'&&e.comment.length<=4000&&typeof e.comment_confirmed==='boolean'&&e.comment_confirmed===Boolean(e.comment);});
}
function getDraft(g){if(drafts.has(g.domain))return drafts.get(g.domain);let d=blank(g);try{const raw=localStorage.getItem(key(g));if(raw){const stored=JSON.parse(raw);if(draftValid(g,stored))d=stored;}}catch(e){storageAvailable=false;}drafts.set(g.domain,d);return d;}
function completion(g){if(g.status!=='published')return 0;const d=getDraft(g);return CONDITIONS.reduce((n,c)=>n+IDS.filter(id=>answerValid(id,d.conditions[c].answers[id],true)).length,0)+(preferenceValid(d.preference,true)?1:0);}
function progressText(g){const d=getDraft(g);const core=CONDITIONS.reduce((n,c)=>n+IDS.filter(id=>answerValid(id,d.conditions[c].answers[id],true)).length,0);return `${core} / 20 strategy answers · ${preferenceValid(d.preference,true)?'1':'0'} / 1 preference`;} 
function notify(text){document.getElementById('message').textContent=text;}
function persist(g){const d=getDraft(g);try{localStorage.setItem(key(g),JSON.stringify(d));storageAvailable=true;}catch(e){storageAvailable=false;}const s=document.getElementById('save-state');if(s)s.textContent=storageAvailable?'Draft saved in this browser. Download JSON for a file copy.':'Browser storage unavailable. Download a draft backup before leaving.';const progress=document.getElementById('attribute-progress');if(progress)progress.textContent=progressText(g);const b=document.getElementById('download-attribute');if(b)b.disabled=completion(g)!==21;drawNavigation();}
function download(name,value){const blob=new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('JSON download requested. Browser drafts remain available. This does not submit data to a server.');}
function navigate(kind,id){active={kind,id};render();document.getElementById('task').scrollIntoView({block:'start'});}
function attributeButton(g,text){const b=el('button',text||`${g.title} questionnaire`,'attribute-nav');b.type='button';b.addEventListener('click',()=>navigate('attribute',g.domain));return b;}
function drawNavigation(){
  const nav=document.getElementById('navigation');nav.replaceChildren();
  for(const g of DATA.attributes){const section=el('section');section.append(el('h2',g.title));const group=el('div',null,'group');
    for(const code of g.task_codes){const task=DATA.tasks.find(t=>t.task_code===code);const button=el('button',null,(active.kind==='task'&&code===active.id?'active ':'')+(task.status==='published'?'':'pending'));button.type='button';button.append(el('span',taskLabel(task)),el('span',task.status==='published'?'Listen':'Pending','done'));button.addEventListener('click',()=>navigate('task',code));group.append(button);}
    const questionnaire=attributeButton(g);if(active.kind==='attribute'&&active.id===g.domain)questionnaire.classList.add('active');questionnaire.append(el('span',g.status==='published'?`${completion(g)} / 21 completed`:'Waiting for all tasks','done'));section.append(group,questionnaire);nav.append(section);
  }
  document.getElementById('coverage').textContent=`${published.length} / ${DATA.tasks.length} tasks published · ${DATA.audio_count} strategy audio files · ${DATA.technical_failure_count} technical failures. ${publishedAttributes.length} / ${DATA.attributes.length} attribute questionnaires available.`;
}
function sourceLabel(source){if(source==='assistant_authored_user_authorized'||source==='assistant_authorized_text')return 'Assistant-authored reply, authorized by the user';if(source==='user_supplied_text')return 'User-supplied text';return source||'Source not recorded';}
function clarificationBox(info){const box=el('section',null,'clarify');box.append(el('h4',`Clarification: ${info.status==='yes'?'Yes':info.status==='no'?'No':'Unknown'}`));if(info.status==='no')box.append(el('p','No clarification question was recorded for this strategy.'));if(info.status==='unknown')box.append(el('p','Insufficient retained evidence to label this as no clarification.'));for(const [i,turn] of info.turns.entries()){const article=el('article');article.append(el('strong',`Clarification ${i+1}`),el('p',`Question: ${turn.question}`,'pre'),el('p',`Reply: ${turn.answer||'(No reply recorded)'}`,'pre'),el('p',sourceLabel(turn.source),'source'));box.append(article);}if(info.evidence_note)box.append(el('p',info.evidence_note,'source'));return box;}
function choice(g,c,id,text,value,special=false){const label=el('label',null,'choice');const radio=el('input');radio.type='radio';radio.name=`${g.domain}-${c}-${id}`;radio.value=special?'unable_to_judge':String(value);const saved=getDraft(g).conditions[c].answers[id];radio.checked=special?saved.status==='unable_to_judge':saved.status==='answered'&&saved.value===value;radio.addEventListener('change',()=>{getDraft(g).conditions[c].answers[id]=special?{status:'unable_to_judge',value:null}:{status:'answered',value};persist(g);});label.append(radio,el('span',text));return label;}
function question(g,c,item){const field=el('fieldset');field.append(el('legend',`${item.id}. ${item.text}`));if(item.help)field.append(el('p',item.help,'help'));const category=item.scale==='category';const options=el('div',null,category?'choices':'choices numeric');if(category){for(const [text,value] of [['Fully met','fully_met'],['Partly met','partly_met'],['Not met','not_met']])options.append(choice(g,c,item.id,text,value));options.append(choice(g,c,item.id,'Unable to judge',null,true));field.append(options);}else{for(let n=1;n<=7;n++)options.append(choice(g,c,item.id,String(n),n));field.append(options);const scale=el('div',null,'scale');const left=item.left||(item.scale==='ease7'?'Very difficult':'Strongly disagree');const right=item.right||(item.scale==='ease7'?'Very easy':'Strongly agree');scale.append(el('span',`1 — ${left}`),el('span',`7 — ${right}`));field.append(scale);const special=el('div',null,'special');special.append(choice(g,c,item.id,'Unable to judge',null,true));field.append(special);}return field;}
function audioPlayer(item,label){const audio=el('audio');audio.controls=true;audio.preload='none';audio.src=item.audio_url;audio.setAttribute('aria-label',label);audio.addEventListener('play',()=>document.querySelectorAll('audio').forEach(other=>{if(other!==audio)other.pause();}));return audio;}
const SETTING_NAMES={speech_rate:'Speech rate',reply_length:'Reply length',tone:'Tone',voice:'Voice',avatar_id:'Tutor model',outfit:'Outfit',jacket_color:'Jacket color',accessory:'Accessory',scale:'Tutor size'};
function settingValue(key,value){if(value===undefined||value===null)return 'Not recorded';if(key==='speech_rate'&&typeof value==='number')return `${value}×`;if(key==='voice'&&typeof value==='string'&&/^voice_[a-z]$/.test(value))return ({voice_a:'Female voice 1',voice_b:'Female voice 2',voice_c:'Female voice 3',voice_d:'Male voice 1',voice_e:'Male voice 2'}[value]||value);return typeof value==='object'?JSON.stringify(value):String(value);}
function resultLabel(result){if(result.status==='stopped')return 'Stopped';if(result.outcome==='unresolved')return 'Unresolved';if(result.outcome==='cancelled')return 'Cancelled';if(result.comparison_available)return result.setting_changes.length?'Settings changed':'No setting change';return 'Recorded outcome';}
function resultBox(t,result){
  const box=el('section',null,'recorded-result');box.append(el('strong',`Recorded result: ${resultLabel(result)}`));
  const before=result.baseline_settings,after=result.settings;const field=t.domain;
  if(after&&Object.hasOwn(after,field)){const target=before&&Object.hasOwn(before,field)?`${settingValue(field,before[field])} → ${settingValue(field,after[field])}`:settingValue(field,after[field]);box.append(el('p',`${SETTING_NAMES[field]||field}: ${target}`));}
  const details=el('details');details.append(el('summary','Recorded outcome and settings'),el('p',`Outcome: ${result.outcome||'Not recorded'} · Status: ${result.status||'Not recorded'}`,'muted'));
  if(after){const table=el('table',null,'settings-table');const head=el('tr');for(const title of ['Setting','Starting state','Recorded result'])head.append(el('th',title));table.append(head);for(const key of [...new Set([...Object.keys(before||{}),...Object.keys(after)])]){const row=el('tr');row.append(el('th',SETTING_NAMES[key]||key),el('td',settingValue(key,before&&before[key])),el('td',settingValue(key,after[key])));table.append(row);}details.append(table);}
  if(!result.comparison_available)details.append(el('p','The earlier release does not retain both settings snapshots, so no change comparison is inferred.','muted'));
  details.append(el('p','These are recorded settings and runtime outcomes, not an automatic judgment that the request was satisfied.','muted'));box.append(details);return box;
}
function systemResponse(result,hasAudio){const details=el('details',null,'system-response');details.append(el('summary','Recorded system response'),el('p',result.message,'muted pre'));if(hasAudio&&result.message.includes('Audio playback is not connected yet'))details.append(el('p','This control message was recorded before the saved audio was generated. The available audio is provided by the player above.','muted'));return details;}
function listeningMaterials(t){
  const section=el('section',null,'task-intro listening-materials');section.append(el('h3','Starting sample'));
  section.append(el('p','Supplied starting-condition material for comparison. This is not an output produced by any of the four strategies. Listen here before comparing the outputs below.','muted'));
  if(t.baseline_audio){section.append(audioPlayer(t.baseline_audio,`${taskLabel(t)} starting sample`));const text=el('details');text.append(el('summary','Starting sample text'),el('div',t.baseline_audio.text,'pre'));section.append(text);}else section.append(el('p','A starting sample was not included in this earlier release.','muted'));
  for(const [index,material] of (t.listening_materials||[]).entries()){const card=el('div',null,'audio-block reference-material');card.append(el('h4',`Reference ${index+1}: ${material.label}`),el('p','Supplied reference material for this task, separate from the strategy outputs.','muted'),audioPlayer(material.audio,`${taskLabel(t)} reference ${index+1}: ${material.label}`));const text=el('details');text.append(el('summary','Reference sample text'),el('div',material.audio.text,'pre'));card.append(text);section.append(card);}
  return section;
}
function renderTask(host,t){
  const g=DATA.attributes.find(g=>g.domain===t.domain);const intro=el('section',null,'task-intro');intro.append(el('div',`${t.title} · ${t.scenario}`,'label'),el('h2',taskLabel(t)),el('strong','Task goal'),el('p',t.goal),el('strong','Keep unchanged'),el('p',t.keep_unchanged));if(t.request_example)intro.append(el('strong','Request example'),el('blockquote',t.request_example));
  if(t.status==='published'){intro.append(el('strong','Submitted request'),el('blockquote',t.request));const followups=t.followup_questions||[];for(const text of [...new Set(followups.map(q=>q.text))]){const matching=followups.filter(q=>q.text===text);intro.append(el('strong','Evaluation question'),el('blockquote',text));intro.append(el('p',matching.every(q=>q.source==='standardized_evaluation_probe')?'Standardized follow-up question used to check the adjustment effect. This was supplied for evaluation, not a spontaneous user request.':'Recorded follow-up question; separate from the original request.','muted'));}}
  intro.append(el('p',`Listening only: no questionnaire is required for this task. After reviewing all ${g.task_codes.length} ${g.title.toLowerCase()} tasks, give one overall evaluation per strategy and one strategy preference for this attribute.`,'attribute-scope'));host.append(intro);
  if(t.status!=='published'){host.append(el('div',t.status_text,'empty'));return;}
  // Legacy sample files remain in audit records; task playback uses actual replies only.
  const grid=el('div',null,'grid');
  for(const c of CONDITIONS){const item=t.conditions[c];const card=el('section',null,'card');card.append(el('h3',`${c} — ${item.name}`),resultBox(t,item.result));const audioBlock=el('div',null,'audio-block');if(item.audio_url){audioBlock.append(audioPlayer(item,`${taskLabel(t)} ${c} output audio`));}else{audioBlock.append(el('p','Technical failure — no output audio was generated.','notice'),el('p',`Recorded error: ${item.technical_failure.error_code}`,'muted'));}audioBlock.append(clarificationBox(item.clarification));if(item.audio_url){const details=el('details');details.append(el('summary',item.purpose==='sample'?'Fixed sample text':'Spoken reply text'),el('div',item.text,'pre'));audioBlock.append(details);}card.append(audioBlock);if(item.result.message)card.append(systemResponse(item.result,Boolean(item.audio_url)));grid.append(card);}
  host.append(grid);const toolbar=el('div',null,'toolbar');const nextCode=g.task_codes[g.task_codes.indexOf(t.task_code)+1];if(nextCode){const next=el('button',`Next task: ${taskLabel(nextCode)}`);next.type='button';next.addEventListener('click',()=>navigate('task',nextCode));toolbar.append(next);}toolbar.append(attributeButton(g,`Open ${g.title.toLowerCase()} questionnaire`));host.append(toolbar);
}
function preference(g){
  const section=el('section',null,'card preference-card');const field=el('fieldset');
  const instruction=MULTI_PREFERENCE?'Select all approaches you prefer (one to four), or choose No preference on its own.':'Choose one option.';
  field.append(el('legend',`Strategy preference — ${g.title}`),el('p',`Across all ${g.task_codes.length} tasks for this attribute, which approaches do you prefer overall? ${instruction} This item is required.`,'help'));
  const options=el('div',null,'choices');const choices=[...CONDITIONS.map(c=>[`${c} — ${NAMES[c]}`,c]),['No preference','no_preference']];
  if(!MULTI_PREFERENCE)choices.push(['Unable to judge',null]);
  function sync(){const saved=getDraft(g).preference;for(const input of options.querySelectorAll('input'))input.checked=MULTI_PREFERENCE?saved.status==='answered'&&saved.value.includes(input.value):input.value==='unable_to_judge'?saved.status==='unable_to_judge':saved.status==='answered'&&saved.value===input.value;}
  for(const [text,value] of choices){const label=el('label',null,'choice');const input=el('input');input.type=MULTI_PREFERENCE?'checkbox':'radio';input.name=`${g.domain}-preference`;input.value=value===null?'unable_to_judge':value;input.addEventListener('change',()=>{getDraft(g).preference=nextPreference(getDraft(g).preference,value,input.checked);sync();persist(g);});label.append(input,el('span',text));options.append(label);}
  sync();field.append(options);section.append(field);return section;
}
function renderAttribute(host,g){
  const intro=el('section',null,'task-intro');intro.append(el('div','Attribute questionnaire','label'),el('h2',g.title),el('p',`Scope: all ${g.task_codes.length} tasks — ${g.task_codes.map(taskLabel).join(', ')}.`,'attribute-scope'),el('p','Review this attribute’s task results, then answer five questions for each of the four approaches and complete the strategy preference item. These are overall judgments across the attribute; do not average or copy earlier task scores.'));
  const links=el('div',null,'listen-links');for(const code of g.task_codes){const b=el('button',`Listen: ${taskLabel(code)}`);b.type='button';b.addEventListener('click',()=>navigate('task',code));links.append(b);}intro.append(links,el('p',`${g.audio_count} strategy audio files · ${g.technical_failure_count} technical failures. Retained clarification and technical-failure evidence is available beside each task’s audio.`,'muted'));
  if(g.technical_failure_count)intro.append(el('p','Some results have no audio because of a recorded technical failure. Consider the available evidence; use “Unable to judge” where you cannot make an overall judgment. No answer is assigned automatically.','notice'));
  const provenance=el('details',null,'source-details');provenance.append(el('summary','Questionnaire scope and sources'),el('p',`${DATA.questionnaire_version}; adapted from ${DATA.source_questionnaire_version}. The wording now refers to all tasks within one attribute. This is not a standard-scale total.`));for(const item of DATA.items)provenance.append(el('p',`${item.id}: ${item.source||'Project item'} ${item.scope_adaptation||''}`));intro.append(provenance);host.append(intro);
  if(g.status!=='published'){host.append(el('div','The attribute questionnaire becomes available when all of its tasks have published results. Published tasks can already be reviewed; unfinished strategy outputs remain hidden.','empty'));return;}
  const grid=el('div',null,'grid');for(const c of CONDITIONS){const card=el('section',null,'card questionnaire-card');card.append(el('h3',`${c} — ${NAMES[c]}`));const form=el('div',null,'questionnaire');for(const item of DATA.items)form.append(question(g,c,item));const commentLabel=el('label','Additional comment about this strategy (optional)','comment-label');const input=el('textarea');input.maxLength=4000;input.value=getDraft(g).conditions[c].extras.comment;input.addEventListener('input',()=>{const extra=getDraft(g).conditions[c].extras;extra.comment=input.value;extra.comment_confirmed=Boolean(input.value);persist(g);});commentLabel.append(input);form.append(commentLabel);card.append(form);grid.append(card);}host.append(grid,preference(g));
  const bar=el('div',null,'toolbar');const progress=el('span',progressText(g),'status');progress.id='attribute-progress';const button=el('button','Download this attribute’s feedback JSON','primary');button.id='download-attribute';button.type='button';button.disabled=completion(g)!==21;button.addEventListener('click',()=>{if(completion(g)!==21)return;download(`${g.domain}-attribute-feedback.json`,getDraft(g));});const saveState=el('span',storageAvailable?'Drafts are stored in this browser. Download JSON for a file copy.':'Browser storage unavailable. Download a draft backup before leaving.','muted');saveState.id='save-state';bar.append(progress,button,saveState);host.append(bar,el('p','No score or preference is prefilled. “Unable to judge” is a separate category, not a score of 4. Earlier per-task drafts remain untouched and are not imported. Downloaded feedback is checked against all task release versions in this attribute.','muted'));
}
function render(){document.querySelectorAll('audio').forEach(a=>a.pause());const host=document.getElementById('task');host.replaceChildren();if(active.kind==='attribute')renderAttribute(host,DATA.attributes.find(g=>g.domain===active.id));else renderTask(host,DATA.tasks.find(t=>t.task_code===active.id));drawNavigation();}
function bundle(kind,groups){return {schema:'tutor-text-attribute-feedback-bundle-v1',batch_id:DATA.batch_id,questionnaire_version:DATA.questionnaire_version,kind,exported_at:new Date().toISOString(),records:groups.map(getDraft)};}
document.getElementById('exportAll').addEventListener('click',()=>download('attribute-feedback-drafts.json',bundle('draft_backup',publishedAttributes)));
document.getElementById('exportComplete').addEventListener('click',()=>{const complete=publishedAttributes.filter(g=>completion(g)===21);if(!complete.length){notify('No complete attribute feedback yet. Each attribute requires 20 strategy answers and one preference. You can download all drafts for backup.');return;}download('completed-attribute-feedback.json',bundle('completed_attributes',complete));});
render();
</script></body></html>'''


def rebase_audio_urls(data, directory, output_directory):
    """Relocate the page without copying or mutating frozen audio/release data."""
    if Path(directory).resolve() == Path(output_directory).resolve():
        return data
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'audio_url' and isinstance(child, str):
                    source = inside(Path(directory).resolve(), unquote(child))
                    value[key] = quote(Path(os.path.relpath(source, output_directory)).as_posix())
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(data)
    return data


def generate(directory, output=None, questionnaire_version=VERSION):
    directory = Path(directory).resolve()
    output = directory / 'REVIEW_AND_QUESTIONNAIRE.html' if output is None else Path(output).resolve()
    if not output.parent.is_dir():
        raise ValueError('Create the destination directory before generating the page.')
    data = rebase_audio_urls(collect(directory, questionnaire_version), directory, output.parent)
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    document = PAGE.replace('__DATA__', serialized)
    temporary = output.with_name(output.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        stream.write(document)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, output)
    return {'file': str(output), 'published_tasks': sum(t['status'] == 'published' for t in data['tasks']),
            'pending_tasks': sum(t['status'] != 'published' for t in data['tasks']),
            'audio_count': data['audio_count'], 'baseline_audio_count': data['baseline_audio_count'],
            'listening_material_count': data['listening_material_count'], 'technical_failure_count': data['technical_failure_count'],
            'questionnaire_version': data['questionnaire_version'], 'provider_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--output', type=Path, help='New HTML destination; source audio and metadata remain unchanged.')
    parser.add_argument('--questionnaire-version', choices=SUPPORTED_VERSIONS, default=VERSION)
    args = parser.parse_args()
    print(json.dumps(generate(args.directory, args.output, args.questionnaire_version), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
