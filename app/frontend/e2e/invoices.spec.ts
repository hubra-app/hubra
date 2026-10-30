import { expect, test } from '@playwright/test'
import { appUrl, EMAIL } from './env'

test('a typed invoice amount is kept, also for a member on a free tier', async ({ page }) => {
  await page.goto(appUrl('finance/invoices'))
  await page.getByRole('button', { name: /Rechnung/ }).first().click()
  const dialog = page.getByRole('dialog')
  // The member picker is the searchable select (the others are read-only).
  const picker = dialog.locator('input.mantine-Select-input:not([readonly])').first()
  await picker.fill(EMAIL.split('@')[0])
  await page.getByRole('option').first().click()

  const amount = dialog.getByPlaceholder('0.00')
  await amount.fill('50')
  // The tier's price preview used to run again on every render and put
  // the tier's price (0 for a free tier) back after a moment.
  await page.waitForTimeout(1500)
  await expect(amount).toHaveValue('50')
})

test('the poll cards fit a narrow phone', async ({ browser }) => {
  const context = await browser.newContext({
    storageState: 'e2e/.auth/state.json',
    viewport: { width: 320, height: 640 },
  })
  const page = await context.newPage()
  await page.goto(appUrl('operations/polls'))
  await page.waitForLoadState('networkidle')
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
  for (const card of await page.locator('.mantine-Paper-root .mantine-Paper-root').all()) {
    const box = await card.boundingBox()
    if (box) expect(box.x + box.width).toBeLessThanOrEqual(320)
  }
  await context.close()
})
