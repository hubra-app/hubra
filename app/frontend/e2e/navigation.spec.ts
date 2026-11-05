import { expect, test } from '@playwright/test'
import { appUrl } from './env'

test('every sidebar entry opens its screen without an error', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto(appUrl('dashboard'))
  const links = page.locator('a.nav-item')
  await expect(links.first()).toBeVisible()
  const hrefs = await links.evaluateAll((as) => as.map((a) => a.getAttribute('href')!))
  expect(hrefs.length).toBeGreaterThan(3)

  for (const href of hrefs) {
    await page.locator(`a.nav-item[href="${href}"]`).first().click()
    await expect(page).toHaveURL(new RegExp(`${href}($|/|\\?)`))
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.getByText('Etwas ist schiefgelaufen')).toHaveCount(0)
  }
  expect(errors).toEqual([])
})

test('sidebar entries are links that can open in a new tab', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  const members = page.locator('a.nav-item[href$="/app/members"]').first()
  await expect(members).toHaveAttribute('href', /\/app\/members$/)
})
