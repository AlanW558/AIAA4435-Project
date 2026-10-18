"""Derive one six-page questionnaire from the existing authored questions."""

import copy
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(source, root=ROOT):
    forms = {form['id']: form for form in source['forms']}
    metadata = [
        dict(id='participant_id', title='研究者提供的参与者编号',
             type='short_text', required=True, max_length=40),
        dict(id='phase', title='本次实验类型', type='single_choice', required=True,
             help='请按研究者的安排选择。', options=copy.deepcopy(source['phase_options']))
    ]
    pages = [dict(id='pre', title='开始前', description='请先阅读研究说明，再决定是否参加。',
                  questions=metadata + copy.deepcopy(forms['pre']['questions']))]
    for block in range(1, 5):
        pages.append(dict(
            id=f'block_{block}', form='block', block=block, title=f'第 {block} 轮结束后',
            description=f'请先完成第 {block} 轮体验，再填写本页。只根据这一轮作答，所有题目都可以跳过。填写后保留此页面，按研究者的安排继续。',
            questions=copy.deepcopy(forms['block']['questions'])))
    pages.append(dict(id='exit', title='全部结束后',
                      description='请回顾刚完成的四轮任务。以下问题都可以跳过，填完后统一提交。',
                      questions=copy.deepcopy(forms['exit']['questions'])))
    pages[-1]['questions'][0]['help'] = '请按本问卷的第 1 至第 4 轮回想。'
    rows = []
    for page_no, page in enumerate(pages, 1):
        for question in page['questions']:
            number = len(rows) + 1
            question['number'] = number
            question['source_field'] = question['id']
            question['id'] = f'{page["id"]}.{question["id"]}'
            question['default'] = None
            question['randomize_options'] = False
            question['score_enabled'] = False
            if number > 3:
                question['display_conditions'] = [{'field': 'pre.consent', 'equals': 'agree'}]
            if question['source_field'] == 'prior_survey_code':
                question['display_conditions'].append({'field': 'pre.prior_link_consent', 'equals': 'yes'})
            question.pop('show_if', None)
            rows.append(dict(question_no=number, page=page_no,
                             form=page.get('form', page['id']), block=page.get('block', ''),
                             source_field=question['source_field'], required=question['required'],
                             unified_id=question['id']))
    result = dict(
        schema_version='appearance-unified-questionnaire-v1',
        content_revision='appearance-survey-v0.1-zh-CN.4-unified',
        language='zh-CN', status='unpublished_draft',
        title='虚拟角色外形修改研究（全流程）',
        description='本问卷按实验顺序分为六页：开始前、四轮体验后的反馈，以及最后的回顾。参与者编号和实验类型只填一次。每轮体验结束后，回到本问卷继续填写，不用重新扫码。请保持页面打开，最后统一提交。除参与者编号、实验类型和参加同意外，其余问题都可以跳过。',
        study_information=source['study_information'],
        pages=pages, page_break_after_questions=[7, 12, 17, 22, 27],
        consent_gate=dict(field='pre.consent', proceed_if='agree', otherwise='结束问卷',
                          platform_storage_status='拒绝后是否保存记录未验证，不承诺零保存。'),
        shared_device=dict(device_limit=False, ip_limit=False, account_limit=False,
                           wechat_limit=False, resume=False, autofill_previous=False,
                           response_quota=None),
        measurement_note=source['measurement_note'],
        export_note='一份答卷对应一人一次实验；按固定分页将四轮评分展开为四条分轮记录，条件从研究者分配表关联。缺失评分保持缺失，不作为零分。')
    assert len(rows) == 32
    assert [row['question_no'] for row in rows if row['required']] == [1, 2, 3]
    (root/'questionnaire_unified.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (root/'unified_field_map.csv').open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Keep page instructions out of the plain question import: add pagination in the editor.
    lines = [result['title'], '', result['description'], '', *source['study_information'], '']
    for page in pages:
        for question in page['questions']:
            kind = '填空题' if question['type'] in ('short_text', 'long_text') else '单选题'
            lines.append(f'{question["number"]}. {question["title"]} [{kind}]')
            if question.get('help'):
                lines.append(question['help'])
            for i, option in enumerate(question.get('options', [])):
                lines.append(f'{chr(65+i)}. {option["label"]}')
            lines.append('')
    (root/'wjx_unified_import.txt').write_text('\n'.join(lines), encoding='utf-8')
    template = root/'questionnaire_unified.template.html'
    if template.exists():
        embedded = json.dumps(result, ensure_ascii=False).replace('</', '<\\/')
        (root/'questionnaire_unified.html').write_text(
            template.read_text(encoding='utf-8').replace('__UNIFIED_SPEC_JSON__', embedded), encoding='utf-8')
    return result


if __name__ == '__main__':
    build(json.loads((ROOT/'questionnaires.json').read_text(encoding='utf-8')))
    print('Wrote one authored questionnaire: 32 questions, 6 pages; no responses generated.')
