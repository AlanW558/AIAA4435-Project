"""Generate authored questionnaire materials; never generate participant responses."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
scale = [{'value': n, 'label': f'{n} — {label}'} for n,label in enumerate(['Strongly disagree','Disagree','Somewhat disagree','Neither agree nor disagree','Somewhat agree','Agree','Strongly agree'],1)]
scale += [{'value': 'cannot_judge', 'label':'Cannot judge / prefer not to answer'}]
def question(id, title, type='single_choice', *, options=None, required=False, **other):
    result = dict(id=id,title=title,type=type,required=required,**other)
    if options is not None:
        result['options']=[dict(value=v,label=l) for v,l in options]
    return result
pre = [
 question('consent','I have read the study information, had an opportunity to ask questions, and agree to take part.', options=[('agree','I agree to take part.'),('decline','I do not agree to take part.')], required=True),
 question('vr_experience','Before today, approximately how many times have you used a VR headset?',options=[('never','Never'),('one_to_two','1–2 times'),('three_to_ten','3–10 times'),('more_than_ten','More than 10 times'),('cannot_recall','Cannot recall / prefer not to answer')]),
 question('prior_prototype_exposure','Before today, have you tried this appearance-customisation prototype?', options=[('no','No'),('yes','Yes'),('unsure','Not sure / prefer not to answer')]),
 question('prior_link_consent','If an anonymous code exists for your earlier course questionnaire, may we link that response to this session?',options=[('yes','Yes, using a code I can provide.'),('no','No.'),('unavailable','I do not have a code / I am not sure.')],help='This is optional. We will not try to identify an anonymous earlier response by its wording.'),
 question('prior_survey_code','Earlier questionnaire code — optional','short_text',show_if={'field':'prior_link_consent','equals':'yes'},max_length=80,help='Enter only an existing anonymous code. Do not enter your name, email address, or phone number.')]
block=[]
for key,title in [('interruption_1to7',"The system’s questions interrupted my task."),('control_1to7','I could control which appearance properties were changed.'),('effort_1to7','Completing the changes required a lot of effort.'),('satisfaction_1to7','I was satisfied with the customisation experience in this block.')]:
    block.append(question(key,title,'rating', options=[(x['value'],x['label']) for x in scale],help='If the system asked no questions in this block, select 1 (strongly disagree).' if key=='interruption_1to7' else None))
block.append(question('block_comment','Is there anything about this block you would like us to know? — optional','long_text',max_length=1000,help='A short comment is enough. Please do not include personal information.'))
exit_questions=[
 question('preferred_block','Which block would you prefer to use for similar appearance changes?',options=[('1','Block 1'),('2','Block 2'),('3','Block 3'),('4','Block 4'),('no_preference','No preference'),('none','I would prefer none of them'),('cannot_judge','Cannot judge / prefer not to answer')],help='Refer to the neutral block numbers shown during the session.'),
 question('preference_reason','What influenced that choice? — optional','long_text',max_length=1000),
 question('helpful_question','Was there a question that helped you make a change? If so, what made it helpful? — optional','long_text',max_length=1000,help='“None” is also a useful answer.'),
 question('unhelpful_question','Was there a question you did not need or could not answer? If so, describe it. — optional','long_text',max_length=1000,help='“None” is also a useful answer.'),
 question('other_feedback','Anything else you would change about making, checking, or undoing appearance changes? — optional','long_text',max_length=1000)]
content={
 'schema_version':'appearance-survey-v0.1','authored_on':'2026-10-18','status':'draft_for_pilot',
 'language':'en','measurement_note':'Four custom single items; not a validated scale and not a combined UX score.',
 'publication_status':'Local artifacts only. No external questionnaire has been created or published by this generator.',
 'participant_ids':{'formal':'P001–P020','pilot':['PILOT01','PILOT02']},
 'session_metadata':{'participant_id':'Researcher-assigned pseudonymous ID. Required.','session_id':'Use the participant-wide study_session_id from Unity client markers, shared across all four blocks; not a per-condition backend session_id. Required.','phase':'Derived from participant ID; never participant-selected.','block':'1–4 for the block form only; participant sees neutral block number.','condition':'Never ask or display; join from the frozen schedule during analysis.'},
 'study_information':[
  'This AIAA4435 course study examines how people make changes to a virtual character’s appearance. You will complete tasks in four blocks and answer short questions about your experience. There are no right or preferred answers.',
  'Participation is voluntary. You may skip opinion questions, take a break, or stop the session. Tell the researcher immediately if you feel uncomfortable, including discomfort from the headset.',
  'We record your task requests, choices, appearance changes, timing, questionnaire answers, and screenshots of the virtual character and interface. This form does not record microphone or camera input. Do not include personal or sensitive information in requests or answers.',
  'Task requests are processed by an external AI service (DeepSeek). These questionnaire responses are kept separate from model prompts. Use only the study ID given by the researcher; do not enter your name or contact details.',
  'The researcher will explain who can access the study data, its storage and retention arrangements, and how to request withdrawal. Please ask any questions before deciding whether to take part.'
 ],
 'forms':[
  {'id':'pre','title':'Character Appearance Study — Before the Session','description':'Please read the study information, then answer the background questions. Consent is required to begin; the background questions are optional.','questions':pre,'consent_gate':{'field':'consent','proceed_if':'agree','otherwise':'End the form without storing answers.'}},
  {'id':'block','title':'Character Appearance Study — After a Block','description':'Please answer only about the block you have just completed. The four statements use the same 1–7 agreement scale. Each answer is optional.','questions':block,'repeat':'After each of the four blocks; same wording and response order.'},
  {'id':'exit','title':'Character Appearance Study — At the End','description':'Think about the four blocks you completed. All questions are optional. Short answers are sufficient.','questions':exit_questions}
 ]}
(ROOT/'questionnaires.json').write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for form in content['forms']:
    lines=[form['title'],'',form['description'],'']
    if form['id']=='pre':
        lines+=content['study_information']+['']
    meta=[question('participant_id','Study ID given by the researcher','short_text',required=True),question('session_id','Session code given by the researcher','short_text',required=True)]
    if form['id']=='block':
        meta.append(question('block','Which block have you just completed?',options=[(str(i),f'Block {i}') for i in range(1,5)],required=True))
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
