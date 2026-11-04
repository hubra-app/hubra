import { defineConfig, devices } from '@playwright/test'
import { STATE, WORKERS } from './e2e/env'

// End-to-end tests against a running stack (see e2e/env.ts):
//   npm run test:e2e
// E2E_WORKERS=3 runs three workers, each with its own club and account
// (e2e/env.ts); CI does that (scripts/e2e-accounts.sh makes the accounts).
// A spec file runs in one worker, top to bottom.
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: WORKERS,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    storageState: STATE,
    locale: 'de-CH',
    trace: 'retain-on-failure',
    // A Chromium that is already installed (PLAYWRIGHT_CHROMIUM=/path/to/chrome).
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
