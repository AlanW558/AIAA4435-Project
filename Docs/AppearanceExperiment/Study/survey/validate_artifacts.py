"""Static/schema validation only; not a claim of browser interaction testing."""
import ast
import csv
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent
spec=json.loads((ROOT/'questionnaires.json').read_text(encoding='utf-8'))
forms={f['id']:f for f in spec['forms']}
assert spec['language']=='zh-CN'
assert spec['content_revision']=='appearance-survey-v0.1-zh-CN.3'
participant_text=list(spec['study_information'])
for form in forms.values():
    participant_text.extend([form['title'],form['description']])
    for question in form['questions']:
        participant_text.extend([question['title'],question.get('help') or ''])
        participant_text.extend(option['label'] for option in question.get('options',[]))
for text in participant_text:
    assert not re.search('[—–]',text),text
    assert not re.search('[A-Za-z]{2,}',text.replace('AIAA4435','').replace('DeepSeek','')),text

assert set(forms)=={'pre','block','exit'}
assert len(forms['block']['questions'])==5
rating_fields=('interruption_1to7','control_1to7','effort_1to7','satisfaction_1to7')
assert tuple(q['id'] for q in forms['block']['questions'][:4])==rating_fields
for f in forms.values():
    ids=[q['id'] for q in f['questions']]
    assert len(ids)==len(set(ids))
    for q in f['questions']:
        assert q['required']==(q['id']=='consent')
        if q.get('type')=='rating':
            assert [o['value'] for o in q['options']]==list(range(1,8))+['cannot_judge']
assert forms['pre']['questions'][-1]['show_if']=={'field':'prior_link_consent','equals':'yes'}
assert forms['pre']['consent_gate']['proceed_if']=='agree'
for script in ('build_forms.py','build_unified_wjx.py','import_responses.py','validate_artifacts.py','session_identity.py'):
    ast.parse((ROOT/script).read_text(encoding='utf-8'))
html=(ROOT/'questionnaire.html').read_text(encoding='utf-8')
assert '__SPEC_JSON__' not in html
assert '<html lang="zh-CN">' in html
class VisibleCopy(HTMLParser):
    def __init__(self):
        super().__init__();self.skip=False;self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip=True
        for key,value in attrs:
            if key in ('aria-label','placeholder') and value:self.text.append(value)
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=False
    def handle_data(self,data):
        if not self.skip:self.text.append(data)
copy=VisibleCopy();copy.feed(html)
for text in copy.text:
    assert not re.search('[—–]',text),text
    assert not re.search('[A-Za-z]{2,}',text.replace('PILOT01','').replace('P001','').replace('DEBUG','')),text

embedded=re.search(r'<script id="spec" type="application/json">(.*?)</script>',html,re.S).group(1)
assert json.loads(embedded)==spec
assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://',html,re.I)
for forbidden in ('fetch(','XMLHttpRequest','localStorage','sessionStorage','sendBeacon('):
    assert forbidden not in html,forbidden
assert 'condition' not in [q['id'] for f in forms.values() for q in f['questions']]
for fid,expected in [('pre',7),('block',8),('exit',7)]:
    text=(ROOT/f'wjx_{fid}_import.txt').read_text(encoding='utf-8')
    assert len(re.findall(r'^\d+\. ',text,re.M))==expected
js=re.findall(r'<script>(.*?)</script>',html,re.S)[0]
node=shutil.which('node')
if node:
    with tempfile.TemporaryDirectory() as d:
        script=Path(d)/'questionnaire.js';script.write_text(js,encoding='utf-8')
        subprocess.run([node,'--check',str(script)],check=True,capture_output=True,text=True)
report={'schema_version':spec['schema_version'],'content_revision':spec['content_revision'],'language':spec['language'],'participant_copy_checks':'中文题干、选项、说明及静态界面文本检查通过','humanizer_review':'humanizer_review.md','static_schema_checks':'passed','python_syntax':'passed','javascript_syntax':'passed' if node else 'not checked: Node unavailable','forms':3,'wjx_questions_including_metadata':{'pre':7,'block':8,'exit':7},'block_rating_items':4,'network_or_automatic_storage':'none in local HTML','browser_interaction':'本脚本不验证浏览器交互；实际操作记录见 browser_creation_status.md','real_responses_generated':0,'online_forms_created_by_this_validator':0}
unified=json.loads((ROOT/'questionnaire_unified.json').read_text(encoding='utf-8'))
pages=unified['pages'];questions=[q for page in pages for q in page['questions']]
assert len(pages)==6 and len(questions)==32 and len({q['id'] for q in questions})==32
assert [q['number'] for q in questions if q['required']]==[1,2,3]
assert unified['page_break_after_questions']==[7,12,17,22,27]
assert questions[6]['display_conditions']==[{'field':'pre.consent','equals':'agree'},{'field':'pre.prior_link_consent','equals':'yes'}]
for q in questions:
    assert q['default'] is None and not q['randomize_options'] and not q['score_enabled']
    for text in [q['title'],q.get('help') or '',*[o['label'] for o in q.get('options',[])]]:
        assert not re.search('[—–]',text),text
        assert not re.search('[A-Za-z]{2,}',text),text
    if q['number']>3:assert {'field':'pre.consent','equals':'agree'} in q['display_conditions']
for page in pages[1:5]:
    assert [q['source_field'] for q in page['questions']]==[q['id'] for q in forms['block']['questions']]
    for q,original in zip(page['questions'],forms['block']['questions']):
        for key in ('title','help','type','options','required','max_length'):
            assert q.get(key)==original.get(key),(q['id'],key)
unified_html=(ROOT/'questionnaire_unified.html').read_text(encoding='utf-8')
assert json.loads(re.search(r'<script id="spec" type="application/json">(.*?)</script>',unified_html,re.S).group(1))==unified
for forbidden in ('fetch(','XMLHttpRequest','localStorage','sessionStorage','sendBeacon('):
    assert forbidden not in unified_html,forbidden
assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://',unified_html,re.I)
if node:
    with tempfile.TemporaryDirectory() as d:
        script=Path(d)/'unified.js';script.write_text(re.findall(r'<script>(.*?)</script>',unified_html,re.S)[0],encoding='utf-8')
        subprocess.run([node,'--check',str(script)],check=True,capture_output=True,text=True)
report['unified']={'content_revision':unified['content_revision'],'pages':6,'questions':32,'required_questions':[1,2,3],'identical_round_items':True,'checks':'passed','browser_evidence':'../../Validation/survey-ui-unified.json'}
(ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
