// Record the actual local Streamlit workflow with generated T018 input only.
// Node22+, Chromium and ffmpeg; no package install, remote host or student input.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const fixture = path.resolve(process.argv[2] || 'tmp/t018/demo/Демо_10_помилок.docx');
const output = path.resolve(process.argv[3] || 'tmp/t019');
const target = 'http://127.0.0.1:8502/';
const video = path.join(output, 'Оформлено_демо_60с.mp4');
if (fs.existsSync(video) || fs.existsSync(path.join(output, 'frames'))) {
  throw new Error('Use a new recording output folder.');
}
fs.mkdirSync(path.join(output, 'frames'), { recursive: true });
fs.mkdirSync(path.join(output, 'download'), { recursive: true });
const source = fs.readFileSync(fixture);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const evidence = { target, input_sha256: hash(source), synthetic: true, steps: [] };
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'oformleno-demo-record-'));
const pause = ms => new Promise(resolve => setTimeout(resolve, Math.max(0, ms)));
const browser = spawn('/usr/bin/chromium', ['--headless=new', '--no-sandbox',
  '--disable-dev-shm-usage', '--disable-background-networking', '--no-first-run',
  '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'],
  { stdio: 'ignore' });
let socket, sequence = 0, recording = false, failure, began = 0;
const pending = new Map();
async function until(label, check, limit = 30000) {
  const end = Date.now() + limit;
  while (Date.now() < end) {
    try { const result = await check(); if (result) return result; } catch {}
    await pause(200);
  }
  throw new Error(`Timeout: ${label}`);
}
function call(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(method + ' timeout')); }, 20000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); },
      reject: error => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression, byValue = true) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: byValue, awaitPromise: true });
  if (result.exceptionDetails) throw new Error('Browser expression failed');
  return byValue ? result.result.value : result.result;
}
const search = `(selector) => {
  const walk = root => [...root.querySelectorAll(selector), ...[...root.querySelectorAll('*')]
    .flatMap(node => node.shadowRoot ? walk(node.shadowRoot)
      : node.tagName === 'IFRAME' && node.contentDocument ? walk(node.contentDocument) : [])];
  return walk(document);
}`;
const query = selector => `(${search})(${JSON.stringify(selector)})`;
const button = label => `${query('button')}.find(n => n.textContent.trim() === ${JSON.stringify(label)})`;
async function click(label) {
  await until(label, () => evaluate(`Boolean(${button(label)} && !${button(label)}.disabled)`));
  await evaluate(`${button(label)}.click(); true`);
}
async function scroll(selector) {
  await evaluate(`${query(selector)}[0].scrollIntoView({block:'center',behavior:'instant'}); true`);
}
async function at(seconds, label, action) {
  await pause(began + seconds * 1000 - Date.now());
  await action();
  const elapsed = (Date.now() - began) / 1000;
  if (elapsed > seconds + 4 || elapsed >= 59.5) {
    throw new Error('Demo action missed its recording window: ' + label);
  }
  evidence.steps.push({ label, elapsed_seconds: elapsed });
  console.log(`Recorded ${label} at ${elapsed.toFixed(1)}s`);
}
async function counts() {
  return evaluate(`(() => {
    const summary = ${query('.summary')}[0];
    const parts = summary.querySelector('.summary-intro').textContent.match(/Знайдено ([0-9]+) .*?, ([0-9]+) можна/);
    return { errors:Number(parts[1]), fixable:Number(parts[2]),
      manual:Number(summary.querySelector('.counts .notice').textContent.match(/: ([0-9]+)/)[1]) };
  })()`);
}
async function frames() {
  for (let index = 0; index < 120 && recording; index++) {
    await pause(began + index * 500 - Date.now());
    const shot = await call('Page.captureScreenshot', { format: 'jpeg', quality: 85,
      captureBeyondViewport: false });
    fs.writeFileSync(path.join(output, 'frames', `frame-${String(index).padStart(4, '0')}.jpg`),
      Buffer.from(shot.data, 'base64'));
  }
  await pause(began + 60000 - Date.now());
}
try {
  const portFile = path.join(profile, 'DevToolsActivePort');
  await until('browser startup', () => fs.existsSync(portFile));
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json())
    .find(item => item.type === 'page');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  socket.addEventListener('message', event => {
    const response = JSON.parse(event.data), handler = pending.get(response.id);
    if (!handler) return;
    pending.delete(response.id);
    if (response.error) handler.reject(new Error('CDP command failed'));
    else handler.resolve(response.result);
  });
  await call('Page.enable'); await call('Runtime.enable'); await call('DOM.enable');
  await call('Emulation.setDeviceMetricsOverride', { width:1440, height:900, deviceScaleFactor:1, mobile:false });
  await call('Browser.setDownloadBehavior', { behavior:'allow', downloadPath:path.join(output, 'download') });
  await call('Page.navigate', { url:target });
  await until('local upload interface', () => evaluate(`${query('input[type=file]')}.length === 1`));
  if (!await evaluate(`${query('#body-text-mode')}[0].value === 'ordinary'`)) {
    throw new Error('Ordinary mode is not selected');
  }
  began = Date.now(); recording = true;
  const capture = frames();
  const actions = (async () => {
    await at(5, 'ordinary mode and upload controls', () => scroll('#body-text-mode'));
    await at(9, 'select generated demo', async () => {
      const input = await evaluate(`${query('input[type=file]')}[0]`, false);
      const description = await call('DOM.describeNode', { objectId:input.objectId });
      await call('DOM.setFileInputFiles', { backendNodeId:description.node.backendNodeId, files:[fixture] });
    });
    await at(12, 'check document', async () => {
      await click('Перевірити документ');
      await until('report', () => evaluate(`${query('.summary')}.length === 1`));
      evidence.before = await counts();
      if (JSON.stringify(evidence.before) !== JSON.stringify({errors:10,fixable:9,manual:7})) {
        throw new Error('Unexpected before counts');
      }
    });
    await at(22, 'font error with evidence', async () => {
      await evaluate(`${query('.rule-group')}.find(n => n.querySelector('.rule-id').textContent === 'R03')
        .scrollIntoView({block:'center',behavior:'instant'}); true`);
    });
    await at(34, 'return to copy action', () => scroll('.summary'));
    await at(40, 'reveal verified copy', async () => {
      await click('Переглянути виправлену копію');
      await until('download', () => evaluate(`${query('a.app-download')}.length === 1`));
      evidence.after = await counts();
      if (JSON.stringify(evidence.after) !== JSON.stringify({errors:1,fixable:0,manual:7})) {
        throw new Error('Unexpected after counts');
      }
      await scroll('.summary');
    });
    await at(47, 'download corrected copy', async () => {
      await evaluate(`${query('a.app-download')}[0].click(); true`);
      const downloaded = path.join(output,'download','Виправлена_копія.docx');
      await until('saved download', () => fs.existsSync(downloaded));
      evidence.corrected_sha256 = hash(fs.readFileSync(downloaded));
      if (evidence.corrected_sha256 === evidence.input_sha256) throw new Error('Unchanged copy');
    });
    await at(52, 'residual caption and manual counts', async () => {
      await evaluate(`${query('.rule-group')}.find(n => n.querySelector('.rule-id').textContent === 'R08')
        .scrollIntoView({block:'start',behavior:'instant'}); true`);
    });
  })();
  const settled = await Promise.allSettled([capture, actions]);
  const rejected = settled.find(result => result.status === 'rejected');
  if (rejected) throw rejected.reason;
  recording = false;
  await click('Очистити результат');
  await until('reset', () => evaluate(`${query('input[type=file]')}.length === 1`));
  if (hash(fs.readFileSync(fixture)) !== evidence.input_sha256) throw new Error('Source changed');
  evidence.actual_backend = true; evidence.source_unchanged = true;
  const subtitles = `1
00:00:00,000 --> 00:00:08,000
Оформлено: прототип перевірки .docx для кафедри ЕОМ.

2
00:00:08,000 --> 00:00:18,000
Звичайний стиль Word: Calibri 12, одинарний інтервал.

3
00:00:18,000 --> 00:00:29,000
10 помилок. 9 можна виправити автоматично.

4
00:00:29,000 --> 00:00:40,000
Місце, фактичне значення та вимога з методички.

5
00:00:40,000 --> 00:00:52,000
Окрема виправлена копія. Оригінал не змінено.

6
00:00:52,000 --> 00:01:00,000
Залишилася 1 помилка та 7 ручних пунктів. Це не повний нормоконтроль.
`;
  fs.writeFileSync(path.join(output,'demo.uk.srt'),subtitles);
  execFileSync('ffmpeg', ['-hide_banner','-loglevel','error','-n','-framerate','2',
    '-i',path.join(output,'frames','frame-%04d.jpg'),'-i',path.join(output,'demo.uk.srt'),
    '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:s','mov_text',
    '-metadata:s:s:0','language=ukr','-disposition:s:0','default',
    '-t','60','-movflags','+faststart',video], {stdio:'pipe'});
  evidence.video_sha256 = hash(fs.readFileSync(video));
  evidence.result = 'PASS';
  console.log('DEMO RECORDING: PASS — actual local backend, 60-second MP4 with Ukrainian subtitles');
} catch (error) {
  recording = false; failure = error;
  evidence.result = 'FAIL'; evidence.error = error.message;
  console.error('DEMO RECORDING: FAIL — ' + error.message);
} finally {
  fs.writeFileSync(path.join(output,'recording-evidence.json'),JSON.stringify(evidence,null,2)+'\n');
  socket?.close(); browser.kill('SIGTERM'); await pause(500);
  if (browser.exitCode === null) browser.kill('SIGKILL');
  fs.rmSync(profile,{recursive:true,force:true});
}
if (failure) process.exitCode = 1;
