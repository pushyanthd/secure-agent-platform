import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    browserName: 'chromium',
    channel: process.platform === 'darwin' ? 'chrome' : undefined,
    viewport: { width: 1440, height: 1100 },
    // Traces include authenticated headers and must not record local credentials.
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
});
