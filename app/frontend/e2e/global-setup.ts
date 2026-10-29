import { chromium, expect } from '@playwright/test'
import { APP_URL, CLUB, EMAIL, PASSWORD, SSO_URL, STATE, appUrl } from './env'

/** Signs in once on the SSO portal and keeps the cookies for every test. */
export default async function globalSetup() {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined,
  })
  const page = await browser.newPage()
  await page.goto(`${SSO_URL}/login?redirect=${encodeURIComponent(appUrl('dashboard'))}`)
  await page.getByLabel(/E-Mail/i).first().fill(EMAIL)
  await page.getByLabel(/Passwort|Password/i).first().fill(PASSWORD)
  await page.keyboard.press('Enter')
  await page.waitForURL(`${APP_URL}/${CLUB}/app/**`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.context().storageState({ path: STATE })
  await browser.close()
}
