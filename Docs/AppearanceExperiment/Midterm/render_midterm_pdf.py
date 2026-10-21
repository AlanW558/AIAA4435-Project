"""Render the authored, self-contained HTML; no remote page or account is accessed."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path='/home/enjixiong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome', headless=True)
        page = await browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1)
        await page.emulate_media(media='print')
        await page.goto((ROOT/'问卷设计说明_中期汇报.html').as_uri(), wait_until='load')
        await page.evaluate('document.fonts.ready')
        audit = await page.evaluate('''() => [...document.querySelectorAll('.page')].map((section, i) => {
          const footerTop = section.querySelector('.footer').getBoundingClientRect().top;
          const contentBottom = Math.max(...[...section.children].filter(el => !el.classList.contains('footer')).map(el => el.getBoundingClientRect().bottom));
          return {page:i+1, gap_to_footer_px:Math.round(footerTop-contentBottom), overflow:contentBottom > footerTop-12};
        })''')
        assert len(audit)==7, audit
        assert not any(item['overflow'] for item in audit), audit
        assert await page.evaluate('document.fonts.check("12px Chinese")')
        await page.pdf(path=str(ROOT/'问卷设计说明_中期汇报.pdf'), print_background=True, prefer_css_page_size=True, display_header_footer=False)
        (ROOT/'pdf_layout_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(audit,ensure_ascii=False))
        await browser.close()

asyncio.run(main())
