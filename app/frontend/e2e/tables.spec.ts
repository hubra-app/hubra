import { expect, test, type Page } from '@playwright/test'
import { appUrl } from './env'

/** The members screen in its table view (it remembers cards or table). */
async function membersTable(page: Page) {
  await page.goto(appUrl('members'))
  await page.getByText(/Tabelle/).first().click()
  await expect(page.locator('table').first()).toBeAttached()
}

test.describe('members table', () => {
  test('shows a table with a header on a laptop', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 })
    await membersTable(page)
    await expect(page.locator('table thead').first()).toBeVisible()
  })

  test('fits a phone screen without sideways scrolling', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 })
    await membersTable(page)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow).toBeLessThanOrEqual(1)
  })

  test('a row opens from the keyboard', async ({ page }) => {
    await membersTable(page)
    const row = page.locator('table tbody tr[tabindex="0"]').first()
    await row.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/app\/members\/\d+/)
  })
})
