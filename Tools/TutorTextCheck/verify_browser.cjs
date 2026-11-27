#!/usr/bin/env node
// Read-only browser acceptance: isolated storage, muted audio, no provider calls.
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

function check(condition, message) { if (!condition) throw new Error(message); }
function sha(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function playwright() {
  if (process.env.PLAYWRIGHT_MODULE) return require(process.env.PLAYWRIGHT_MODULE);
  try { return require('playwright'); } catch (_) {
    return require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
  }
}

async function verify(directory, output, screenshotDirectory) {
  const root = fs.realpathSync(directory);
  const html = path.join(root, 'REVIEW_AND_QUESTIONNAIRE.html');
  const htmlHash = sha(html);
  for (const destination of [output, screenshotDirectory].filter(Boolean)) {
    const relative = path.relative(root, path.resolve(destination));
    check(relative.startsWith('..' + path.sep) || path.isAbsolute(relative), 'Browser QA output must stay outside the inspected batch.');
  }
  if (screenshotDirectory) fs.mkdirSync(screenshotDirectory, {recursive: true});
  const server = http.createServer((request, response) => {
    if (!['GET', 'HEAD'].includes(request.method)) { response.writeHead(405); response.end(); return; }
    try {
      const url = new URL(request.url, 'http://localhost');
      if (url.pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
      const file = fs.realpathSync(path.join(root, decodeURIComponent(url.pathname)));
      check(file.startsWith(root + path.sep), 'Path is outside batch.');
      const stat = fs.statSync(file); check(stat.isFile(), 'Not a file.');
      const types = {'.html': 'text/html; charset=utf-8', '.wav': 'audio/wav', '.json': 'application/json'};
      response.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream',
        'Content-Length': stat.size, 'Cache-Control': 'no-store'});
      if (request.method === 'HEAD') response.end(); else fs.createReadStream(file).pipe(response);
    } catch (_) { response.writeHead(404); response.end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  let browser;
  try {
    const {chromium} = playwright();
    const installed = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
    const executablePath = process.env.CHROME_EXECUTABLE || (fs.existsSync(chromium.executablePath()) ? chromium.executablePath() : installed);
    browser = await chromium.launch({headless: true, executablePath,
      args: ['--mute-audio', '--disable-background-networking', '--disable-component-update', '--no-first-run']});
    const context = await browser.newContext({viewport: {width: 1440, height: 1050}, acceptDownloads: false});
    const origin = `http://127.0.0.1:${server.address().port}`;
    const externalRequests = [];
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin === origin) return route.continue();
      externalRequests.push(route.request().url()); return route.abort();
    });
    await context.addInitScript(() => {
      window.__releaseQA = {reads: [], writes: 0};
      const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
      Storage.prototype.getItem = function(key) { window.__releaseQA.reads.push(key); return get.call(this, key); };
      Storage.prototype.setItem = function(key, value) { window.__releaseQA.writes++; return set.call(this, key, value); };
    });
    const page = await context.newPage();
    const jsErrors = [], consoleErrors = [];
    page.on('pageerror', error => jsErrors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    await page.goto(origin + '/REVIEW_AND_QUESTIONNAIRE.html', {waitUntil: 'load'});
    const data = await page.locator('#report-data').evaluate(element => JSON.parse(element.textContent));
    check(data.tasks.length === 32 && data.tasks.every(t => t.status === 'published'), 'All 32 tasks must be published.');
    check(data.audio_count === 128 && data.technical_failure_count === 0, 'Expected 128 actual strategy reply audios without technical failure.');
    check(data.baseline_audio_count === 0 && data.listening_material_count === 0, 'Fixed samples cannot be part of this batch.');
    const loaded = [], screenshots = [];
    for (let i = 0; i < data.tasks.length; i++) {
      const task = data.tasks[i];
      await page.locator('nav .group button').nth(i).click();
      check((await page.locator('#task h2').textContent()).includes(task.display_code), `Task navigation mismatch: ${task.task_code}`);
      const visible = await page.locator('#task').innerText();
      for (const label of ['Task goal', 'Keep unchanged', 'Request example']) check(visible.includes(label), `${task.task_code}: missing ${label}`);
      check(!visible.includes('Supplied Starting Context') && !visible.includes('Starting sample'), `${task.task_code}: obsolete fixed sample/context shown.`);
      check(await page.locator('#task audio').count() === 4, `${task.task_code}: expected four audio controls.`);
      for (const [j, condition] of ['E', 'A', 'N', 'S'].entries()) {
        const card = await page.locator('#task .grid > .card').nth(j).innerText();
        const info = task.conditions[condition].clarification;
        check(card.includes(`Clarification: ${info.status === 'yes' ? 'Yes' : 'No'}`), `${task.task_code}/${condition}: missing clarification label.`);
        for (const turn of info.turns) check(card.includes(turn.question) && card.includes(turn.answer), `${task.task_code}/${condition}: clarification text is not visible.`);
      }
      const metadata = await page.locator('#task audio').evaluateAll(elements => Promise.all(elements.map(audio => new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Audio metadata timeout')), 15000);
        const done = () => { clearTimeout(timer); resolve({src: audio.src, duration: audio.duration, error: audio.error?.code || null}); };
        if (audio.readyState >= 1) return done();
        audio.addEventListener('loadedmetadata', done, {once: true});
        audio.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Audio metadata error')); }, {once: true});
        audio.preload = 'metadata'; audio.load();
      }))));
      check(metadata.every(audio => !audio.error && Number.isFinite(audio.duration) && audio.duration > 0), `${task.task_code}: invalid browser audio metadata.`);
      loaded.push(...metadata);
      if (screenshotDirectory && !screenshots.length && Object.values(task.conditions).some(card => card.clarification.status === 'yes')) {
        const file = path.resolve(screenshotDirectory, 'task-with-clarification.png');
        check(!fs.existsSync(file), 'Refusing to overwrite an existing QA screenshot.');
        await page.screenshot({path: file, fullPage: true, animations: 'disabled'});
        screenshots.push({kind: 'task_with_clarification', task_code: task.task_code, file, sha256: sha(file)});
      }
    }
    const decoded = await page.evaluate(async urls => {
      const context = new OfflineAudioContext(1, 1, 24000), results = [];
      for (const url of urls) {
        const response = await fetch(url); if (!response.ok) throw new Error('Audio fetch failed');
        const buffer = await context.decodeAudioData(await response.arrayBuffer());
        let nonzero = false;
        for (const value of buffer.getChannelData(0)) if (value !== 0) { nonzero = true; break; }
        results.push({duration: buffer.duration, sampleRate: buffer.sampleRate, channels: buffer.numberOfChannels, frames: buffer.length, nonzero});
      }
      return results;
    }, loaded.map(audio => audio.src));
    check(decoded.length === 128 && decoded.every(audio => audio.nonzero && audio.frames > 0), 'A browser-decoded WAV was empty or silent.');
    const questionnaires = [];
    for (let i = 0; i < data.attributes.length; i++) {
      await page.locator('nav .attribute-nav').nth(i).click();
      const groups = await page.locator('#task fieldset').count();
      const checked = await page.locator('#task input:checked').count();
      const empty = await page.locator('#task textarea').evaluateAll(elements => elements.every(e => e.value === ''));
      check(groups === 21 && checked === 0 && empty, `${data.attributes[i].domain}: questionnaire is not blank with 21 answer groups.`);
      if (['attribute-summary-feedback-v2','attribute-summary-feedback-v3'].includes(data.questionnaire_version)) {
        for (let c = 0; c < 4; c++) {
          const a0 = page.locator('#task .questionnaire-card').nth(c).locator('fieldset').first();
          const labels = await a0.locator('.numeric .choice').allTextContents();
          check(JSON.stringify(labels.map(text => text.trim())) === JSON.stringify(['1','2','3','4','5','6','7']), 'A0 must offer all seven numeric scores.');
          const text = await a0.innerText();
          check(text.includes('1 — Not at all') && text.includes('7 — Completely') && text.includes('Unable to judge'), 'A0 anchors or separate unable-to-judge option missing.');
        }
      }
      if (data.questionnaire_version === 'attribute-summary-feedback-v3') {
        const preference=page.locator('#task .preference-card');
        check(await preference.locator('input[type=checkbox]').count() === 5, 'Preference requires four strategies and exclusive No preference.');
        check(await preference.locator('input[type=radio]').count() === 0, 'New preference must not use single-choice radios.');
        const text=await preference.innerText();
        check(!text.includes('Unable to judge') && !text.includes('Unable to compare'), 'Removed preference option remains visible.');
      }
      check(await page.locator('#download-attribute').isDisabled(), 'Incomplete questionnaire can be exported as complete.');
      questionnaires.push({domain: data.attributes[i].domain, groups, checked, optional_comments_empty: empty});
      if (screenshotDirectory && i === 0) {
        const file = path.resolve(screenshotDirectory, 'attribute-questionnaire-blank.png');
        check(!fs.existsSync(file), 'Refusing to overwrite an existing QA screenshot.');
        await page.screenshot({path: file, fullPage: true, animations: 'disabled'});
        screenshots.push({kind: 'blank_attribute_questionnaire', domain: data.attributes[i].domain, file, sha256: sha(file)});
      }
    }
    const widths = [];
    for (const width of [1440, 600, 390]) {
      await page.setViewportSize({width, height: 1050});
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      check(!overflow, `Questionnaire horizontal overflow at ${width}px.`); widths.push(width);
    }
    const storage = await page.evaluate(() => ({...window.__releaseQA, entries: localStorage.length}));
    check(storage.writes === 0 && storage.entries === 0, 'Blank navigation unexpectedly changed browser storage.');
    check(storage.reads.every(key => key.startsWith('tutor-text-attribute-feedback-v1:' + data.batch_id + ':')), 'Page accessed a legacy or unrelated feedback namespace.');
    check(!jsErrors.length && !consoleErrors.length && !externalRequests.length, 'Browser reported JavaScript, console or unexpected external request errors.');
    check(sha(html) === htmlHash, 'Published HTML changed during browser verification.');
    const result = {schema: 'tutor-text-browser-qa-v1', passed: true, checked_at: new Date().toISOString(),
      batch_id: data.batch_id, questionnaire_version: data.questionnaire_version, provider_calls: 0, readonly_actual_data: true,
      task_count: 32, strategy_audio: 128, decoded_audio: decoded.length, audio_played: false,
      all_audio_metadata_loaded: true, clarification_labels_and_text_checked: true,
      questionnaires, required_blank_answers: 84, local_storage_writes: storage.writes, local_storage_entries: storage.entries,
      viewport_widths_no_overflow: widths, js_errors: jsErrors, console_errors: consoleErrors,
      external_requests: externalRequests.length, html_sha256: htmlHash, screenshots,
      limitation: 'Browser decoding and blank-form checks do not assess perceived voice quality or task success.'};
    if (output) { fs.mkdirSync(path.dirname(output), {recursive: true}); fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n', {flag: 'wx'}); }
    return result;
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const directory = args[0], index = args.indexOf('--output'), screenshotIndex = args.indexOf('--screenshot-dir');
  check(directory && !directory.startsWith('--'), 'Usage: node verify_browser.cjs BATCH_DIR [--output OUTSIDE_BATCH.json] [--screenshot-dir OUTSIDE_BATCH]');
  verify(directory, index >= 0 ? path.resolve(args[index + 1]) : null,
    screenshotIndex >= 0 ? path.resolve(args[screenshotIndex + 1]) : null)
    .then(result => process.stdout.write(JSON.stringify(result, null, 2) + '\n'))
    .catch(error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
}
module.exports = {verify};
