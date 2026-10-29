import { defineConfig, devices } from '@playwright/test'
import { STATE } from './e2e/env'

// End-to-end tests against a running stack (see e2e/env.ts):
//   npm run test:e2e
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
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
