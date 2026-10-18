"""Static/schema validation only; not a claim of browser interaction testing."""
import ast
import csv
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=json.loads((ROOT/'questionnaires.json').read_text(encoding='utf-8'))
forms={f['id']:f for f in spec['forms']}
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
for script in ('build_forms.py','import_responses.py','validate_artifacts.py'):
    ast.parse((ROOT/script).read_text(encoding='utf-8'))
html=(ROOT/'questionnaire.html').read_text(encoding='utf-8')
assert '__SPEC_JSON__' not in html
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
report={'schema_version':spec['schema_version'],'static_schema_checks':'passed','python_syntax':'passed','javascript_syntax':'passed' if node else 'not checked: Node unavailable','forms':3,'wjx_questions_including_metadata':{'pre':7,'block':8,'exit':7},'block_rating_items':4,'network_or_automatic_storage':'none in local HTML','browser_interaction':'not verified; built-in browser tool failed before JavaScript execution','real_responses_generated':0,'online_forms_created':0}
(ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
