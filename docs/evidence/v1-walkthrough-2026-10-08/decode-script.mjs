import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs';
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const output = resolve('artifacts/v1-walkthrough-2026-10-08');
const seconds = [5, 40, 61, 75, 94, 114, 133, 159];
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
await page.goto(pathToFileURL(output + '/walkthrough.webm').href);
await page.waitForFunction(() => {const v = document.querySelector('video'); return v && v.readyState >= 2;});
const metadata = await page.locator('video').evaluate(v => {v.pause(); v.controls = false; return {duration: v.duration, width: v.videoWidth, height: v.videoHeight};});
for (const second of seconds) {
  await page.locator('video').evaluate((v, second) => new Promise(done => {v.addEventListener('seeked', done, {once: true}); v.currentTime = second;}), second);
  await page.locator('video').screenshot({path: output + '/frame-' + second + '.png'});
}
writeFileSync(output + '/playback-review.json', JSON.stringify({metadata, decoded_seconds: seconds}, null, 2) + '\n');
console.log(JSON.stringify(metadata));
await browser.close();
