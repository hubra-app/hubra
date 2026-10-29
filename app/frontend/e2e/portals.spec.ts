import { expect, test } from '@playwright/test'
import { CLUB, MANAGE_URL, SSO_URL } from './env'

test('the SSO portal lists the clubs the account belongs to', async ({ page }) => {
  await page.goto(`${SSO_URL}/clubs`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText(new RegExp(CLUB, 'i')).first()).toBeVisible()
})

test('the manager portal opens for a platform admin', async ({ page }) => {
  await page.goto(MANAGE_URL)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText('Etwas ist schiefgelaufen')).toHaveCount(0)
})
