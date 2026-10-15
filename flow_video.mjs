// z1 流年動畫：用無頭瀏覽器開啟 z1，依 flow.json 的命盤參數排盤。
//   node flow_video.mjs script <flow.json> <out.json>
//       → 輸出旁白句子（以網站目前版本產生）
//   node flow_video.mjs render <flow.json> <durations.json> <fps> | ffmpeg -f image2pipe ...
//       → 依實際語音長度逐格輸出 JPEG 到 stdout，並在 stderr 印出時間軸 JSON
import { chromium } from 'playwright';
import fs from 'node:fs';

const [mode, jobPath, arg2, arg3] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(jobPath, 'utf8'));
const url = job.url || 'https://kftseng2oo1.github.io/z1/';

const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const page = await browser.newPage({ viewport: { width: 420, height: 900 } });
page.on('pageerror', e => console.error('[pageerror]', e.message));
await page.goto(url, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts && document.fonts.ready);

// 排盤
await page.evaluate((inp) => {
    const set = (id, v) => { const el = document.getElementById(id); if (el && v !== undefined && v !== '') el.value = String(v); };
    set('solarYear', inp.solarY);
    set('solarMonth', inp.solarM);
    document.getElementById('solarMonth').dispatchEvent(new Event('change'));
    set('solarDay', inp.solarD);
    set('birthHour', inp.hour);
    set('gender', inp.gender);
    set('flowYear', inp.flowYear);
    set('personName', inp.name);
    runChart();
}, job.input);

if (mode === 'script') {
    const sents = await page.evaluate(() => fvBuildScenes().scenes.flatMap(s => s.sents.map(x => x.text)));
    fs.writeFileSync(arg2, JSON.stringify(sents, null, 1));
    await browser.close();
    process.exit(0);
}

if (mode === 'render') {
    const durs = JSON.parse(fs.readFileSync(arg2, 'utf8'));
    const fps = Number(arg3 || 24);
    const timeline = await page.evaluate((durs) => {
        window.__D = fvBuildScenes(durs);
        window.__cv = document.createElement('canvas');
        window.__cv.width = FV.W; window.__cv.height = FV.H;
        window.__ctx = window.__cv.getContext('2d');
        return { total: __D.total, sents: __D.scenes.flatMap(s => s.sents.map(x => ({ text: x.text, start: x.start, dur: x.dur }))) };
    }, durs);
    console.error(JSON.stringify(timeline));
    const frames = Math.ceil((timeline.total + 0.5) * fps);
    for (let i = 0; i < frames; i++) {
        const b64 = await page.evaluate((t) => {
            fvRenderAt(__ctx, __D, t);
            return __cv.toDataURL('image/jpeg', 0.9).split(',')[1];
        }, Math.min(i / fps, timeline.total - 0.01));
        const buf = Buffer.from(b64, 'base64');
        if (!process.stdout.write(buf)) await new Promise(r => process.stdout.once('drain', r));
    }
    await browser.close();
    process.exit(0);
}

console.error('usage: node flow_video.mjs script|render ...');
process.exit(1);
