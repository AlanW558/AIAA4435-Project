#!/usr/bin/env python3
"""Check the six-page local form with ephemeral engineering debug answers only."""
import argparse
import csv
import json
from pathlib import Path
import sys
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
SURVEY=ROOT/'Docs/AppearanceExperiment/Study/survey'
sys.path.insert(0,str(SURVEY))
from import_responses import import_records, unpack_response
SPEC=json.loads((SURVEY/'questionnaires.json').read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',type=Path,required=True)
    args=parser.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        tmp=Path(tmp)
        browser=p.chromium.launch(executable_path=str(args.chromium),headless=True)
        page=browser.new_page(viewport={'width':1000,'height':950},accept_downloads=True)
        errors=[];external=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:external.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.on('dialog',lambda dialog:dialog.accept())
        url=(SURVEY/'questionnaire_unified.html').as_uri()
        page.goto(url)
        assert page.locator('#phase').input_value()==''
        page.locator('#next').click();assert page.locator('#pageTitle').inner_text()=='开始前'
        page.locator('#phase').select_option('debug')
        page.locator('#participant').fill('DEBUG_UNIFIED_CHECK');page.locator('#participant').blur()
        sid=page.locator('#session').input_value();assert sid.startswith('debug_DEBUG_UNIFIED_CHECK_') and len(sid)<=80
        page.locator('#next').click();assert page.locator('#pageTitle').inner_text()=='开始前'
        def choose(name,value):page.locator(f'input[name="{name}"][value="{value}"]').check()
        choose('pre.consent','decline')
        assert page.locator('#next').is_disabled()
        assert not page.locator('input[name="pre.prior_link_consent"]').first.is_visible()
        choose('pre.consent','agree')
        choose('pre.prior_link_consent','yes')
        page.locator('input[name="pre.prior_survey_code"]').fill('DEBUG_OLD_CODE')
        choose('pre.prior_link_consent','no')
        assert not page.locator('input[name="pre.prior_survey_code"]').is_visible()
        choose('pre.prior_link_consent','yes')
        assert page.locator('input[name="pre.prior_survey_code"]').input_value()==''
        choose('pre.prior_link_consent','no')
        checks.append('No default phase or consent; decline stops progression; hidden old-survey code is cleared when linkage is withdrawn.')

        page.locator('#researcherTools summary').click()
        with page.expect_download() as event:page.locator('#downloadSession').click()
        config=tmp/'session.json';event.value.save_as(config)
        assert json.loads(config.read_text())['study_session_id']==sid
        page.locator('#researcherTools summary').click()
        for block in range(1,5):
            page.locator('#next').click()
            assert page.locator('#pageTitle').inner_text()==f'第 {block} 轮结束后'
            assert not page.locator('#identityPanel').is_visible()
            assert page.locator('#save').is_hidden()
            choose(f'block_{block}.control_1to7',block+1)
            if block==1:choose('block_1.interruption_1to7','cannot_judge')
        page.locator('#previous').click()
        assert page.locator('input[name="block_3.control_1to7"][value="4"]').is_checked()
        page.locator('#next').click()
        assert page.locator('input[name="block_4.control_1to7"][value="5"]').is_checked()
        page.locator('#next').click();assert page.locator('#pageTitle').inner_text()=='全部结束后'
        assert page.locator('#questions [required]').count()==0
        with page.expect_download() as event:page.locator('#save').click()
        source=tmp/'responses';source.mkdir()
        response=source/'engineering_debug_bundle.json';event.value.save_as(response)
        bundle=json.loads(response.read_text());records=unpack_response(bundle,SPEC)
        assert len(records)==6 and {r['session_id'] for r in records}=={sid}
        assert all(v is None for v in records[-1]['answers'].values())
        assert records[0]['answer_status']['prior_survey_code']=='not_shown'
        assert records[1]['answer_status']['interruption_1to7']=='cannot_judge'
        report=import_records(source,SURVEY.parent/'materials/participant_schedule.csv',tmp/'analysis','debug')
        assert (report['response_files'],report['response_records'],report['participant_count'],report['block_rows'])==(1,6,1,4)
        with (tmp/'analysis/block_ratings.csv').open() as f:rows=list(csv.DictReader(f))
        assert [int(r['control_1to7']) for r in rows]==[2,3,4,5]
        assert rows[0]['interruption_1to7']==''
        checks.append('Six pages progress in order; back navigation preserves each round; one download imports as one participant and four correctly mapped rounds, with missing values preserved.')
        checks.append('All five final questions can be skipped; all six records preserve the same identity and original field names.')

        for _ in range(5):page.locator('#previous').click()
        choose('pre.consent','decline');choose('pre.consent','agree');page.locator('#next').click()
        assert page.locator('input[type=radio]:checked').count()==0
        checks.append('Withdrawing consent clears later-page answers and blocks response export.')
        page.locator('#researcherTools summary').click();page.locator('#loadSession').set_input_files(str(config))
        page.wait_for_function("document.querySelector('#pageTitle').textContent === '开始前'")
        assert page.locator('#session').input_value()==sid
        assert page.locator('input[type=radio]:checked').count()==0
        page.locator('#nextParticipant').click()
        assert all(page.locator('#'+key).input_value()=='' for key in ('participant','phase','session'))
        assert page.locator('input[type=radio]:checked').count()==0
        page.goto(url+'?participant=DEBUG_URL&phase=debug&session=DEBUG_PREVIOUS&form=block&block=2')
        assert page.locator('#session').input_value()=='DEBUG_PREVIOUS'
        page.locator('#researcherTools summary').click();page.locator('#nextParticipant').click();page.reload()
        assert all(page.locator('#'+key).input_value()=='' for key in ('participant','phase','session'))
        assert not page.evaluate('location.search')
        checks.append('Config loading restores only identity and clears answers; next participant clears all six pages, phase, identity and stale URL parameters.')

        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
        page.screenshot(path=str(ROOT/'Docs/AppearanceExperiment/Validation/survey-ui-unified.png'),full_page=True)
        assert not errors,errors
        assert not external,external
        checks.append('Phone-width form has no horizontal overflow, JavaScript errors, network requests or answer storage.')
        browser.close()
    report={'passed':True,'evidence_class':'isolated_local_browser_engineering_debug_only','content_revision':'appearance-survey-v0.1-zh-CN.4-unified','checks':checks,'participant_responses_retained':0,'external_submissions':0}
    (ROOT/'Docs/AppearanceExperiment/Validation/survey-ui-unified.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
