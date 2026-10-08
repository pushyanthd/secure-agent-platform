// Real console capture with authored fixtures. No traces, HAR, or credential exports.
import { chromium, expect } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:net';
import { readFileSync, mkdirSync, openSync, closeSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { createHash } from 'node:crypto';

const root = resolve(import.meta.dirname, '../..');
const output = resolve(process.argv[2] || join(root, 'artifacts/walkthrough-2026-10-07'));
mkdirSync(output); // Fresh destinations only; failed recordings remain reviewable.
const directory = join(output, 'private-control');
const python = process.env.AGENTGUARD_PYTHON || join(root, '.venv/bin/python');
const driver = join(root, 'frontend/tests/control_fixture.py');
const log = openSync(join(output, 'private-server.log'), 'w');
const observations = [];
const errors = [];
const started = Date.now();
let server, browser, context;
const socket = createServer();
await new Promise((done) => socket.listen(0, '127.0.0.1', done));
const port = socket.address().port;
await new Promise((done) => socket.close(done));
const origin = `http://127.0.0.1:${port}`;
function fixture(operation, ...args) {
  return execFileSync(python, [driver, root, directory, operation, ...args], {
    cwd: root,
    encoding: 'utf8',
    timeout: 20_000,
  });
}
async function stop() {
  if (server && server.exitCode === null && server.signalCode === null) {
    const stopped = new Promise((done) => server.once('exit', done));
    server.kill('SIGTERM');
    await stopped;
  }
}
async function start() {
  server = spawn(
    python,
    [
      '-m',
      'agentguard.cli',
      'api-serve',
      '--settings',
      join(directory, 'settings.json'),
      '--credentials',
      join(directory, 'credentials.json'),
    ],
    { cwd: root, stdio: ['ignore', log, log] },
  );
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error('Recording API exited');
    try {
      if ((await fetch(origin)).ok) return;
    } catch {
      /* Startup only. */
    }
    await delay(100);
  }
  throw new Error('Recording API startup timed out');
}
function record(check, result) {
  observations.push({ check, result, seconds: (Date.now() - started) / 1000 });
}
async function submit(page, scenario) {
  await page.getByLabel('Scenario', { exact: true }).selectOption(scenario);
  const response = page.waitForResponse(
    (r) => r.url() === `${origin}/api/runs` && r.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Start defended run' }).click();
  const episode = (await (await response).json()).episode_id;
  await expect(page.getByText(episode, { exact: true })).toBeVisible();
  return episode;
}
async function state(page, value) {
  await expect(
    page.getByRole('region', { name: 'Selected run' }).getByText(value, { exact: true }),
  ).toBeVisible();
}
const escape = (s) =>
  String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
try {
  fixture('init', String(port));
  const token = readFileSync(join(directory, 'operator.token'), 'utf8').trim();
  await start();
  browser = await chromium.launch();
  context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
    recordVideo: { dir: join(output, 'video'), size: { width: 1440, height: 1100 } },
  });
  const page = await context.newPage();
  page.on('pageerror', (error) => errors.push(error.message));
  const video = page.video();
  async function card(title, lines, seconds) {
    // Cards are separate explanatory pages, never overlays altering application behavior.
    await page.goto('about:blank');
    await page.setContent(`<html><body style="margin:0;background:#102127;color:#eef6f1;
      font-family:system-ui;padding:110px 140px"><p style="color:#89d3ae;letter-spacing:3px">
      SECURE AGENT PLATFORM | PORTFOLIO WALKTHROUGH</p><h1 style="font-size:50px">${escape(title)}</h1>
      ${lines.map((line) => `<p style="font-size:28px;line-height:1.6">${escape(line)}</p>`).join('')}
      </body></html>`);
    record('chapter', title);
    await delay(seconds * 1000);
  }
  await card(
    'The model proposes. The application authorizes.',
    [
      'A local workplace-agent laboratory using synthetic documents, tickets and shares.',
      'Console demonstration: scripted fixtures, zero fresh-model benchmark trials.',
      'V1 candidate regression: 20/20 clean and 38/38 attacked workflows succeeded.',
    ],
    20,
  );
  await page.goto(origin);
  await expect(page.getByLabel('Access token')).toHaveAttribute('type', 'password');
  await page.getByLabel('Access token').fill(token);
  await page.getByRole('button', { name: 'Connect to workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Run supervision' })).toBeVisible();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  await delay(10_000);
  const episode = await submit(page, 'authorized-shared-write');
  const paused = JSON.parse(fixture('advance'));
  if (paused.status !== 'WAITING_APPROVAL') throw new Error('Approval did not pause');
  await state(page, 'waiting approval');
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await expect(page.getByRole('heading', { name: 'Exact action' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve exact action' })).toBeDisabled();
  await expect(page.getByText('Office hours are at 15:00 UTC.', { exact: true })).toBeVisible();
  await page.getByText('Original task and authorization binding', { exact: true }).click();
  await page.getByRole('heading', { name: 'Exact action' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(output, 'approval.png'), fullPage: true });
  record('exact_action_requires_acknowledgment', true);
  await delay(25_000);
  await stop();
  await expect(page.getByText('Connection interrupted.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reject action' })).toBeDisabled();
  record('api_stopped_review_disabled', true);
  await delay(8_000);
  await start();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve exact action' }).click();
  await expect(page.getByText('Action approved.', { exact: false })).toBeVisible();
  if (JSON.parse(fixture('advance')).status !== 'COMPLETED') throw new Error('Run did not finish');
  await state(page, 'completed');
  const before = JSON.parse(fixture('count_tickets', episode)).count;
  fixture('advance');
  const after = JSON.parse(fixture('count_tickets', episode)).count;
  if (before !== 1 || after !== 1) throw new Error('Effect count differs');
  record('one_committed_ticket_before_and_after_idle_worker', { before, after });
  await page.getByRole('region', { name: 'Selected run' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(output, 'completed.png'), fullPage: true });
  await delay(15_000);
  const denied = await submit(page, 'unauthorized-read');
  fixture('advance');
  await state(page, 'completed');
  await expect(page.locator('.step-marker.deny')).toHaveCount(1);
  await page.getByRole('heading', { name: 'Execution timeline' }).scrollIntoViewIfNeeded();
  record('unauthorized_read_denied_in_real_gateway', { episode: denied });
  await page.screenshot({ path: join(output, 'denied-read.png'), fullPage: true });
  await delay(20_000);
  const cancelled = await submit(page, 'launch-scope');
  await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm cancellation' }).click();
  await state(page, 'cancelled');
  fixture('advance');
  const count = JSON.parse(fixture('count_tickets', cancelled)).count;
  if (count !== 0) throw new Error('Cancelled run committed an effect');
  record('cancelled_queued_run_no_ticket', { count });
  await page.screenshot({ path: join(output, 'cancelled.png'), fullPage: true });
  await delay(15_000);
  // No credentials should exist in rendered text; no request headers are captured.
  if ((await page.locator('body').innerText()).includes(token)) throw new Error('Token rendered');
  const gate = JSON.parse(
    readFileSync(join(root, 'docs/evidence/release-v1-2026-09-27/gate.json')),
  );
  if (gate.status !== 'FAIL' || gate.recorded_episodes !== 400)
    throw new Error('Release provenance changed');
  const comparisonPath = join(
    root,
    'docs/evidence/experimental-v1-candidate-2026-10-08/assessment.json',
  );
  const comparison = JSON.parse(readFileSync(comparisonPath));
  await card(
    'Measure task outcomes and execution boundaries.',
    [
      `Declared V1 candidate regression: ${comparison.counts.clean_success}/${comparison.counts.clean} clean; ${comparison.counts.attacked_success}/${comparison.counts.attacked} attacked.`,
      `All ${comparison.independently_regraded} outcomes independently regraded; opt-in resource guard.`,
      'Separate measured runs cover live recovery, orphan cleanup and storage exhaustion.',
      'Exposed synthetic workflows, one model and seed. Full evaluation history is linked.',
    ],
    25,
  );
  await card(
    'Inspect the evidence. Reproduce the boundaries.',
    [
      'README -> architecture, case study, system card and complete evaluation publications.',
      'make portfolio-check: fresh environment, locked dependencies, checks and portable state grades.',
      'This capture verifies fixture-mode UI behavior. It does not rerun inference or Docker containment.',
      'V1 local engineering platform. Independent external reproduction remains open.',
    ],
    20,
  );
  if (errors.length) throw new Error('Browser errors occurred');
  await context.close();
  await video.saveAs(join(output, 'walkthrough.webm'));
  await browser.close();
  browser = undefined;
  const files = [
    'frontend/scripts/record_walkthrough.mjs',
    'frontend/tests/control_fixture.py',
    'frontend/src/main.tsx',
    'docs/evidence/release-v1-2026-09-27/gate.json',
    'docs/evidence/experimental-v1-candidate-2026-10-08/assessment.json',
  ];
  writeFileSync(
    join(output, 'capture.json'),
    JSON.stringify(
      {
        version: 'portfolio-fixture-capture-v1',
        mode: 'authored_fixture',
        fresh_model_trials: 0,
        edited_video: false,
        audio: false,
        viewport: { width: 1440, height: 1100 },
        elapsed_seconds: (Date.now() - started) / 1000,
        checks: observations,
        page_errors: errors,
        source_sha256: Object.fromEntries(
          files.map((f) => [
            f,
            createHash('sha256')
              .update(readFileSync(join(root, f)))
              .digest('hex'),
          ]),
        ),
        limits: [
          'API restart is not a worker-crash test.',
          'Idle worker invocation is not replay of a committed generation.',
          'Cancellation is before worker execution.',
          'No live-model or containment evidence from this video.',
        ],
      },
      null,
      2,
    ) + '\n',
  );
  console.log(JSON.stringify({ output, checks: observations.length, page_errors: errors.length }));
} finally {
  if (browser) await browser.close();
  await stop();
  closeSync(log);
}
