"""Generate authored questionnaire materials; never generate participant responses."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
scale = [{'value': n, 'label': f'{n}：{label}'} for n,label in enumerate(['非常不同意','不同意','比较不同意','说不上同意或不同意','比较同意','同意','非常同意'],1)]
scale += [{'value': 'cannot_judge', 'label':'无法判断／不想回答'}]
def question(id, title, type='single_choice', *, options=None, required=False, **other):
    result = dict(id=id,title=title,type=type,required=required,**other)
    if options is not None:
        result['options']=[dict(value=v,label=l) for v,l in options]
    return result
pre = [
 question('consent','我已阅读研究说明，有机会向研究者提问，并同意参加本次研究。', options=[('agree','我同意参加。'),('decline','我不同意参加。')], required=True),
 question('vr_experience','在今天之前，你大约使用过多少次虚拟现实头显？',options=[('never','从未用过'),('one_to_two','1 至 2 次'),('three_to_ten','3 至 10 次'),('more_than_ten','10 次以上'),('cannot_recall','记不清／不想回答')]),
 question('prior_prototype_exposure','在今天之前，你是否试用过这套修改虚拟角色外形的原型？', options=[('no','没有'),('yes','有'),('unsure','不确定／不想回答')]),
 question('prior_link_consent','如果你之前填写的课程问卷有匿名编号，你是否同意我们用这个编号，将那份回答与本次实验记录对应起来？',options=[('yes','同意，我可以提供已有的匿名编号。'),('no','不同意。'),('unavailable','我没有匿名编号／不确定。')],help='这项关联由你自愿选择。我们不会根据旧问卷的措辞猜测填写者的身份。'),
 question('prior_survey_code','旧问卷的匿名编号','short_text',show_if={'field':'prior_link_consent','equals':'yes'},max_length=80,help='请只填写已有的匿名编号。可以留空，不要填写姓名、邮箱或手机号。')]
block=[]
for key,title in [('interruption_1to7',"系统的提问打断了我完成任务的过程。"),('control_1to7','我能控制哪些外形特征会被修改。'),('effort_1to7','完成这些修改需要我投入很多精力。'),('satisfaction_1to7','我对这一轮修改外形的体验感到满意。')]:
    block.append(question(key,title,'rating', options=[(x['value'],x['label']) for x in scale],help='如果这一轮系统没有提问，请选 1（非常不同意）。' if key=='interruption_1to7' else None))
block.append(question('block_comment','关于这一轮体验，你还有什么想补充的吗？','long_text',max_length=1000,help='可以留空。简单写几句即可，请不要填写个人信息。'))
exit_questions=[
 question('preferred_block','如果以后还要做类似的外形修改，你更愿意使用哪一轮的系统？',options=[('1','第 1 轮'),('2','第 2 轮'),('3','第 3 轮'),('4','第 4 轮'),('no_preference','没有特别偏好'),('none','这几轮的系统我都不想用'),('cannot_judge','无法判断／不想回答')],help='请按实验中显示的轮次选择。'),
 question('preference_reason','你为什么这样选择？','long_text',max_length=1000),
 question('helpful_question','有没有哪次提问帮你完成了修改？如果有，它帮在什么地方？','long_text',max_length=1000,help='可以留空，也可以回答“没有”。'),
 question('unhelpful_question','有没有哪次提问让你觉得没必要，或者不知道怎么回答？如果有，请描述一下。','long_text',max_length=1000,help='可以留空，也可以回答“没有”。'),
 question('other_feedback','对于修改外形、检查结果或撤销操作，你还有什么改进建议？','long_text',max_length=1000)]
content={
 'schema_version':'appearance-survey-v0.1','authored_on':'2026-10-18','status':'draft_for_pilot',
 'language':'zh-CN','content_revision':'appearance-survey-v0.1-zh-CN.1','measurement_note':'四项均为自拟的单题指标，未经量表验证，分别分析，不合成为体验总分。',
 'publication_status':'本生成器只制作本地文件，不创建或发布外部问卷。',
 'participant_ids':{'formal':'P001–P020','pilot':['PILOT01','PILOT02']},
 'session_metadata':{'participant_id':'研究者分配的参与者编号，必填。','session_id':'必填，使用 Unity 客户端记录中整场实验共用的 study_session_id。四轮使用同一个编号，不填写各条件的后端 session_id。','phase':'根据参与者编号确定，不由参与者选择。','block':'仅用于每轮结束后的问卷，填写 1 至 4；参与者只看到轮次。','condition':'不提问、不展示；分析时依据已冻结的分配表关联。'},
 'study_information':[
  '这是 AIAA4435 课程的一项研究，想了解大家如何修改虚拟角色的外形。你将完成四轮任务，并回答一些关于使用体验的问题。回答没有对错，请按实际情况和感受填写。',
  '参加研究完全自愿。你可以跳过体验问题，随时休息或结束实验。如果感到不适，包括佩戴头显引起的不适，请立即告诉研究者。',
  '我们会记录你提出的修改要求、操作选择、外形变化、用时、问卷回答，以及虚拟角色和界面的截图。本表单不录音，也不调用摄像头。请不要在指令或回答中填写个人信息或敏感信息。',
  '你的修改要求会交给外部人工智能服务 DeepSeek 处理。问卷回答与模型收到的指令分开保存。请只使用研究者给你的参与者编号，不要填写姓名或联系方式。',
  '研究者会说明谁能访问数据、数据存在哪里、保存多久，以及如何申请撤回。有疑问的话，请先询问，再决定是否参加。'
 ],
 'forms':[
  {'id':'pre','title':'虚拟角色外形修改研究：实验开始前','description':'请先阅读研究说明，再决定是否参加。只有同意参加后才继续实验，其他问题都可以跳过。','questions':pre,'consent_gate':{'field':'consent','proceed_if':'agree','otherwise':'结束填写，不保存回答。'}},
  {'id':'block','title':'虚拟角色外形修改研究：每轮结束后','description':'请只根据刚完成的这一轮作答。四道评分题都使用 1 至 7 分，表示你对这句话的同意程度。每道题都可以跳过。','questions':block,'repeat':'四轮结束后各填写一次，题目措辞和选项顺序保持一致。'},
  {'id':'exit','title':'虚拟角色外形修改研究：全部结束后','description':'请回顾刚完成的四轮任务。所有问题都可以跳过，简单写几句即可。','questions':exit_questions}
 ]}
(ROOT/'questionnaires.json').write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for form in content['forms']:
    lines=[form['title'],'',form['description'],'']
    if form['id']=='pre':
        lines+=content['study_information']+['']
    meta=[question('participant_id','研究者提供的参与者编号','short_text',required=True),question('session_id','研究者提供的本次实验编号','short_text',required=True)]
    if form['id']=='block':
        meta.append(question('block','你刚完成的是第几轮？',options=[(str(i),f'第 {i} 轮') for i in range(1,5)],required=True))
    for n,q in enumerate(meta+form['questions'],1):
        label='填空题' if q['type'] in ('short_text','long_text') else '单选题'
        lines.append(f'{n}. {q["title"]} [{label}]')
        if q.get('help'): lines.append(q['help'])
        if q.get('options'): lines += [f'{chr(65+i)}. {o["label"]}' for i,o in enumerate(q['options'])]
        lines.append('')
    (ROOT/f'wjx_{form["id"]}_import.txt').write_text('\n'.join(lines),encoding='utf-8')
template = ROOT/'questionnaire.template.html'
if template.exists():
    embedded = json.dumps(content,ensure_ascii=False).replace('</','<\\/')
    (ROOT/'questionnaire.html').write_text(template.read_text(encoding='utf-8').replace('__SPEC_JSON__',embedded),encoding='utf-8')
print('Wrote authored questionnaires, three import drafts, and local HTML when its template exists; no responses generated.')
