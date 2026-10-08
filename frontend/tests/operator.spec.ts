import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import type { ChildProcess } from 'node:child_process';
import { readFileSync, mkdtempSync, mkdirSync, unlinkSync, openSync, closeSync } from 'node:fs';
import { createServer } from 'node:net';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(import.meta.dirname, '../..');
const python = process.env.AGENTGUARD_PYTHON || join(root, '.venv/bin/python');
const driver = join(root, 'frontend/tests/control_fixture.py');
let directory: string, origin: string, operator: string, observer: string;
let server: ChildProcess | undefined;
let log: number;

function fixture(operation: string, ...args: string[]) {
  return execFileSync(python, [driver, root, directory, operation, ...args], {
    cwd: root,
    encoding: 'utf8',
    timeout: 20_000,
  });
}
async function stop() {
  if (server && server.exitCode === null && server.signalCode === null) {
    const stopped = new Promise<void>((resolve) => server!.once('exit', () => resolve()));
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
    if (server.exitCode !== null)
      throw new Error('API failed to start; inspect the browser-test server log.');
    try {
      if ((await fetch(origin)).ok) return;
    } catch {
      /* Startup only. */
    }
    await delay(100);
  }
  throw new Error('API startup timed out');
}
async function login(page: Page, token = operator) {
  await page.goto(origin);
  await page.getByLabel('Access token').fill(token);
  await page.getByRole('button', { name: 'Connect to workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Run supervision' })).toBeVisible();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
}
async function submit(page: Page, scenario = 'authorized-shared-write') {
  await page.getByLabel('Scenario', { exact: true }).selectOption(scenario);
  const response = page.waitForResponse(
    (response) => response.url() === `${origin}/api/runs` && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Start defended run' }).click();
  const id = (await response).json();
  const episode = (await id).episode_id as string;
  await expect(page.getByText(episode, { exact: true })).toBeVisible();
  return episode;
}
async function waiting(page: Page) {
  const id = await submit(page);
  expect(JSON.parse(fixture('advance')).status).toBe('WAITING_APPROVAL');
  await expect(
    page
      .getByRole('region', { name: 'Selected run' })
      .getByText('waiting approval', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await expect(page.getByRole('heading', { name: 'Exact action' })).toBeVisible();
  return id;
}

test.beforeAll(async () => {
  const socket = createServer();
  await new Promise<void>((resolve) => socket.listen(0, '127.0.0.1', resolve));
  const address = socket.address();
  if (!address || typeof address === 'string') throw new Error('No free port');
  const port = address.port;
  await new Promise<void>((resolve) => socket.close(() => resolve()));
  const parent = join(root, 'artifacts/browser-tests');
  mkdirSync(parent, { recursive: true });
  const session = mkdtempSync(join(parent, 'session-'));
  directory = join(session, 'control');
  fixture('init', String(port));
  operator = readFileSync(join(directory, 'operator.token'), 'utf8').trim();
  observer = readFileSync(join(directory, 'observer.token'), 'utf8').trim();
  origin = `http://127.0.0.1:${port}`;
  log = openSync(join(session, 'server.log'), 'w');
  await start();
});
test.afterAll(async () => {
  await stop();
  if (log !== undefined) closeSync(log);
  for (const file of ['operator.token', 'observer.token', 'credentials.json']) {
    try {
      unlinkSync(join(directory, file));
    } catch {
      /* Setup may have failed. */
    }
  }
});

test('approve the exact action after API restart and commit it once', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await login(page);
  const id = await waiting(page);
  await expect(page.getByRole('button', { name: 'Approve exact action' })).toBeDisabled();
  await expect(page.getByText('Office hours are at 15:00 UTC.', { exact: true })).toBeVisible();
  await page.getByText('Original task and authorization binding', { exact: true }).click();
  await expect(page.getByText('gateway-v3', { exact: true })).toBeVisible();
  await page.screenshot({ path: join(directory, '../approval-desktop.png'), fullPage: true });
  await stop();
  await expect(page.getByText('Connection interrupted.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reject action' })).toBeDisabled();
  await start();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve exact action' }).click();
  await expect(page.getByText('Action approved.', { exact: false })).toBeVisible();
  expect(JSON.parse(fixture('advance')).status).toBe('COMPLETED');
  await expect(
    page.getByRole('region', { name: 'Selected run' }).getByText('completed', { exact: true }),
  ).toBeVisible();
  expect(JSON.parse(fixture('count_tickets', id)).count).toBe(1);
  fixture('advance');
  expect(JSON.parse(fixture('count_tickets', id)).count).toBe(1);
  await expect(
    page.getByText('Execution finished. Task success is determined separately', { exact: false }),
  ).toBeVisible();
  await page.screenshot({ path: join(directory, '../completed-desktop.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('reject leaves no ticket and cancellation prevents future effects', async ({ page }) => {
  await login(page);
  const id = await waiting(page);
  await page.getByRole('button', { name: 'Reject action' }).click();
  await expect(page.getByText('Action rejected.', { exact: false })).toBeVisible();
  fixture('advance');
  expect(JSON.parse(fixture('count_tickets', id)).count).toBe(0);
  const queued = await submit(page, 'launch-scope');
  await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm cancellation' }).click();
  await expect(
    page.getByRole('region', { name: 'Selected run' }).getByText('cancelled', { exact: true }),
  ).toBeVisible();
  fixture('advance');
  expect(JSON.parse(fixture('count_tickets', queued)).count).toBe(0);
});

test('changed resource rejects the displayed approval without an effect', async ({ page }) => {
  await login(page);
  const id = await waiting(page);
  fixture('change_resource', id);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve exact action' }).click();
  await expect(page.getByRole('alert')).toContainText('changed or expired');
  await expect(page.getByRole('heading', { name: 'Exact action' })).toHaveCount(0);
  expect(JSON.parse(fixture('count_tickets', id)).count).toBe(0);
  await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm cancellation' }).click();
});

test('expired approval cannot be approved from the browser', async ({ page }) => {
  await login(page);
  const id = await waiting(page);
  await page.getByRole('button', { name: 'Close details' }).click();
  fixture('expire', id);
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await expect(page.getByRole('button', { name: 'Approve exact action' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Reject action' })).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm cancellation' }).click();
});

test('hostile approval text is inert and mobile layout stays within the viewport', async ({
  page,
}) => {
  await login(page);
  const id = await waiting(page);
  await page.getByRole('button', { name: 'Close details' }).click();
  const hostile =
    '<img id="injected" src=x onerror="window.attackerExecuted=true"><script>window.attackerExecuted=true</script>';
  fixture('hostile', id, hostile);
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await expect(page.getByText(hostile, { exact: true })).toBeVisible();
  expect(await page.locator('#injected').count()).toBe(0);
  expect(await page.evaluate(() => 'attackerExecuted' in window)).toBe(false);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: join(directory, '../approval-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'Cancel run', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm cancellation' }).click();
});

test('document share exposes exact source and commits only after approval', async ({ page }) => {
  await login(page);
  const id = await submit(page, 'reviewed-document-share');
  expect(JSON.parse(fixture('advance')).status).toBe('WAITING_APPROVAL');
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await expect(
    page.locator('.action-fields').getByText('shares.request', { exact: true }),
  ).toBeVisible();
  await page.getByText('Document to share · release', { exact: true }).click();
  await expect(page.getByText('Release checklist approved.', { exact: true })).toBeVisible();
  await expect(page.getByText('Version 1 · internal', { exact: true })).toBeVisible();
  expect(JSON.parse(fixture('count_shares', id)).count).toBe(0);
  await page.screenshot({ path: join(directory, '../share-approval.png'), fullPage: true });
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve exact action' }).click();
  await expect(page.getByText('Action approved.', { exact: false })).toBeVisible();
  expect(JSON.parse(fixture('advance')).status).toBe('COMPLETED');
  expect(JSON.parse(fixture('count_shares', id)).count).toBe(1);
});

test('listed ticket update finishes with the expected version', async ({ page }) => {
  await login(page);
  const id = await submit(page, 'ticket-maintenance');
  await expect(page.locator('.scope-list').getByText('atlas-1', { exact: true })).toBeVisible();
  expect(JSON.parse(fixture('advance')).status).toBe('COMPLETED');
  await expect(
    page.getByRole('region', { name: 'Selected run' }).getByText('completed', { exact: true }),
  ).toBeVisible();
  const tickets = JSON.parse(fixture('tickets', id));
  expect(tickets.find((ticket: { id: string }) => ticket.id === 'atlas-1').version).toBe(2);
  expect(tickets.find((ticket: { id: string }) => ticket.id === 'orion-1').version).toBe(1);
});

test('ticket review shows the trusted edit scope and preserves its sibling', async ({ page }) => {
  await login(page);
  const id = await submit(page, 'reviewed-ticket-correction');
  await expect(page.locator('.scope-list').getByText('notice-1', { exact: true })).toBeVisible();
  expect(JSON.parse(fixture('advance')).status).toBe('WAITING_APPROVAL');
  await page.getByRole('button', { name: 'Inspect action' }).click();
  await page.getByText('Original task and authorization binding', { exact: true }).click();
  const scope = page.locator('.scope-details').filter({
    has: page.getByText('Original task and authorization binding', { exact: true }),
  });
  await expect(scope.getByText('Editable tickets', { exact: true })).toBeVisible();
  await expect(scope.getByText('notice-1', { exact: true })).toBeVisible();
  const before = JSON.parse(fixture('tickets', id));
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve exact action' }).click();
  await expect(page.getByText('Action approved.', { exact: false })).toBeVisible();
  expect(JSON.parse(fixture('advance')).status).toBe('COMPLETED');
  const after = JSON.parse(fixture('tickets', id));
  expect(after.find((ticket: { id: string }) => ticket.id === 'notice-1').version).toBe(2);
  expect(after.filter((ticket: { id: string }) => ticket.id !== 'notice-1')).toEqual(
    before.filter((ticket: { id: string }) => ticket.id !== 'notice-1'),
  );
});

test('observer has no review credential and cannot submit or cancel', async ({ page }) => {
  await login(page);
  await waiting(page);
  await page.getByRole('button', { name: 'Disconnect' }).click();
  await login(page, observer);
  await expect(page.getByRole('button', { name: 'Start defended run' })).toBeDisabled();
  await expect(page.getByText('Operator review required', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Inspect action' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Cancel run', exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Exact action' })).toHaveCount(0);
});

test('credentials are absent from storage and URLs; reload clears session', async ({ page }) => {
  await login(page);
  const saved = await page.evaluate(() => ({
    local: { ...localStorage },
    session: { ...sessionStorage },
    cookies: document.cookie,
    url: location.href,
  }));
  expect(saved.local).toEqual({});
  expect(saved.session).toEqual({});
  expect(saved.cookies).toBe('');
  expect(saved.url).toBe(`${origin}/`);
  expect(await page.locator('input[type=password]').count()).toBe(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Connect to your console' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Run supervision' })).toHaveCount(0);
});

test('lost submission response retries the same idempotency key', async ({ page }) => {
  await login(page);
  const keys: string[] = [];
  let intercepted = false;
  await page.route('**/api/runs', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    keys.push(route.request().headers()['idempotency-key']);
    if (!intercepted) {
      intercepted = true;
      await route.fetch();
      await route.abort('failed');
    } else await route.continue();
  });
  await page.getByLabel('Scenario', { exact: true }).selectOption('launch-scope');
  await page.getByRole('button', { name: 'Start defended run' }).click();
  await expect(page.getByRole('button', { name: 'Retry submission' })).toBeVisible();
  await expect(page.getByLabel('Scenario', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Retry submission' }).click();
  await expect(page.getByRole('button', { name: 'Start defended run' })).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test('in-flight responses cannot restore a disconnected session', async ({ page }) => {
  await login(page);
  await submit(page, 'launch-scope');
  let intercepted: (() => void) | undefined;
  const waiting = new Promise<void>((resolve) => {
    intercepted = resolve;
  });
  await page.route('**/timeline', async (route) => {
    intercepted?.();
    await delay(500);
    try {
      await route.continue();
    } catch {
      /* Logout aborts the request. */
    }
  });
  await waiting;
  await page.getByRole('button', { name: 'Disconnect' }).click();
  await delay(700);
  await expect(page.getByRole('heading', { name: 'Connect to your console' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Selected run' })).toHaveCount(0);
});
