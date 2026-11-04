import { expect, test } from '@playwright/test'
import { enableModule } from './api'
import { MANAGE_URL, appUrl } from './env'

// Lists keep one row of controls: search, one "Filter" button with every
// filter and the sort order, and the active filters as removable chips.

test('club app: a filter is set in the panel and removed from its chip', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  await enableModule(page, 'finance')
  await page.goto(appUrl('finance/invoices'))
  const main = page.getByRole('main')
  // No filter chips at rest, and no status chips in the toolbar.
  await expect(main.getByRole('radio', { name: 'Bezahlt' })).toHaveCount(0)

  await main.getByRole('button', { name: /^Filter/ }).click()
  const status = page.getByRole('radiogroup', { name: 'Status' })
  await status.getByRole('radio', { name: 'Bezahlt' }).click()
  await expect(status.getByRole('radio', { name: 'Bezahlt' })).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('button', { name: 'Fertig' }).click()

  const remove = main.getByRole('button', { name: 'Status: Bezahlt entfernen' })
  await expect(remove).toBeVisible()
  await remove.click()
  await expect(remove).toHaveCount(0)
})

test('club app: members sort from the column header', async ({ page }) => {
  await page.goto(appUrl('members'))
  await page.getByRole('img', { name: 'Liste' }).first().click()
  const header = page.locator('table thead').getByRole('button', { name: /Mitglied/ })
  await header.click()
  await expect(header).toHaveAttribute('aria-sort', 'descending')
  // The order also shows as a chip, so it is visible in the card view too.
  await expect(
    page.getByRole('main').getByRole('button', { name: 'Sortieren: Name Z–A entfernen' }),
  ).toBeVisible()
})

test('manage: the clubs list has the same Filter panel', async ({ page }) => {
  await page.goto(`${MANAGE_URL}/app/tenants`)
  await page.getByRole('main').getByRole('button', { name: /^Filter/ }).click()
  await expect(page.getByRole('radiogroup', { name: 'Plan' })).toBeVisible()
  await expect(page.getByRole('radiogroup', { name: 'Status' })).toBeVisible()
})

test('club app: short records are a plain list, not a table', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  await enableModule(page, 'finance')
  for (const path of ['finance/categories', 'finance/external-parties']) {
    await page.goto(appUrl(path))
    await expect(page.getByRole('main').locator('h1').first()).toBeVisible()
    await expect(page.getByRole('main').locator('table')).toHaveCount(0)
  }
})
