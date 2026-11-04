import { chromium, expect, type Browser } from '@playwright/test'
import { APP_URL, PASSWORD, SSO_URL, WORKERS, accountFor, stateFor } from './env'

/** Signs one account in on the SSO portal and keeps its cookies. */
async function signIn(browser: Browser, index: number) {
  const { club, email } = accountFor(index)
  const context = await browser.newContext()
  const page = await context.newPage()
  const dashboard = `${APP_URL}/${club}/app/dashboard`
  await page.goto(`${SSO_URL}/login?redirect=${encodeURIComponent(dashboard)}`)
  await page.getByLabel(/E-Mail/i).first().fill(email)
  await page.getByLabel(/Passwort|Password/i).first().fill(PASSWORD)
  await page.keyboard.press('Enter')
  await page.waitForURL(`${APP_URL}/${club}/app/**`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await context.storageState({ path: stateFor(index) })
  await context.close()
}

/** Signs every worker's account in once; each worker's tests reuse its cookies. */
export default async function globalSetup() {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined,
  })
  await Promise.all(Array.from({ length: WORKERS }, (_, i) => signIn(browser, i)))
  await browser.close()
}
