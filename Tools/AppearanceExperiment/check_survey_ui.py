#!/usr/bin/env python3
"""Exercise local HTML in isolated Chromium; temporary debug fixtures only.

Requires Playwright in the invoking Python environment and an existing Chromium.
Never connects to WJX, submits a web form or retains downloaded answers.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
SURVEY=ROOT/'Docs/AppearanceExperiment/Study/survey'
sys.path.insert(0,str(SURVEY))
from import_responses import validate_record
SPEC=json.loads((SURVEY/'questionnaires.json').read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',type=Path,required=True)
    args=parser.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(args.chromium),headless=True)
        page=browser.new_page(viewport={'width':1000,'height':950},accept_downloads=True)
        errors=[]; page.on('pageerror',lambda err:errors.append(str(err)))
        page.on('dialog',lambda dialog:dialog.accept())
        page.goto((SURVEY/'questionnaire.html').as_uri())
        assert page.locator('#phase').input_value()==''
        assert not page.locator('#blockLabel').is_visible()
        assert page.locator('#session').get_attribute('readonly') is not None
        assert not page.locator('#session').is_visible()
        page.locator('#phase').select_option('debug');page.locator('#participant').fill('DEBUG_UI_CHECK');page.locator('#participant').blur()
        sid=page.locator('#session').input_value();assert sid.startswith('debug_DEBUG_UI_CHECK_') and len(sid)<=80
        page.locator('input[name=consent][value=decline]').check()
        assert page.locator('#save').is_disabled()
        page.locator('input[name=consent][value=agree]').check()
        checks.append('Phase is required without default; session generated; declined local consent cannot download answers.')
        page.locator('#researcherTools summary').click()
        with page.expect_download() as event:page.locator('#downloadSession').click()
        config_path=Path(tmp)/'debug_session.json';event.value.save_as(config_path)
        assert json.loads(config_path.read_text())['study_session_id']==sid
        page.locator('#researcherTools summary').click()

        def download():
            with page.expect_download() as event:page.locator('#save').click()
            path=Path(tmp)/'temporary_debug_response.json';event.value.save_as(path)
            value=json.loads(path.read_text());validate_record(value,SPEC)
            assert value['phase']=='debug' and value['session_id']==sid
            return value

        download()
        page.locator('#formSelect').select_option('block');page.locator('#block').select_option('1')
        page.locator('input[name=control_1to7][value="5"]').check()
        value=download();assert value['answers']['control_1to7']==5
        page.locator('#formSelect').select_option('exit')
        assert not page.locator('#blockLabel').is_visible()
        value=download();assert all(v is None for v in value['answers'].values())
        checks.append('Pre/block/exit debug downloads pass the real importer and preserve one session; all five exit items can be skipped.')
        page.locator('#nextParticipant').click()
        assert page.locator('#participant').input_value()==page.locator('#phase').input_value()==page.locator('#session').input_value()==''
        assert page.locator('input[type=radio]:checked').count()==0
        page.locator('#researcherTools summary').click();page.locator('#loadSession').set_input_files(str(config_path))
        page.wait_for_function("document.querySelector('#session').value !== ''")
        assert page.locator('#session').input_value()==sid
        page.locator('#nextParticipant').click();page.locator('#phase').select_option('debug');page.locator('#participant').fill('DEBUG_UI_CHECK');page.locator('#participant').blur()
        assert page.locator('#session').input_value()!=sid
        checks.append('Next participant clears identity and answers; same code gets a fresh session; explicit config reload restores the exact prior ID.')
        page.goto((SURVEY/'questionnaire.html').as_uri()+'?participant=DEBUG_URL&phase=debug&session=DEBUG_LEGACY_SESSION&form=block&block=2')
        assert page.locator('#session').input_value()=='DEBUG_LEGACY_SESSION'
        page.locator('#nextParticipant').click();page.reload()
        assert page.locator('#participant').input_value()=='' and page.locator('#session').input_value()==''
        checks.append('Legacy launch links remain compatible; next participant removes URL identity so refresh cannot resurrect the previous person.')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(ROOT/'Docs/AppearanceExperiment/Validation/survey-ui-v3.png'),full_page=True)
        assert not errors,errors
        checks.append('Phone-width page has no horizontal overflow and no JavaScript errors.')
        browser.close()
    report={'passed':True,'evidence_class':'isolated_local_browser_engineering_debug_only','checks':checks,'participant_responses_retained':0,'external_submissions':0}
    (ROOT/'Docs/AppearanceExperiment/Validation/survey-ui-v3.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
