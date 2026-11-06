import { expect, test } from '@playwright/test'
import { APP_URL, CLUB, appUrl } from './env'

// Invoice mails used to link to <app>/invoices, which has no club and
// showed the 404 page.
test('the old invoice mail link opens the personal start page of the club', async ({ page }) => {
  await page.goto(appUrl('dashboard')) // remembers the club on this device
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  await page.goto(`${APP_URL}/invoices`)
  await expect(page).toHaveURL(`${APP_URL}/${CLUB}/app/dashboard/me`)
  await expect(page.getByText('Seite nicht gefunden')).toHaveCount(0)
})

test('the 404 page offers to report the broken link', async ({ page }) => {
  await page.goto(`${APP_URL}/no-such-page`)
  await expect(page.getByRole('heading', { name: 'Seite nicht gefunden' })).toBeVisible()
  const report = page.getByRole('link', { name: 'Problem melden' })
  const where = encodeURIComponent(`${APP_URL}/no-such-page`)
  await expect(report).toHaveAttribute('href', new RegExp(`/melden\\?where=${where}$`))
})
