import { expect, test } from '@playwright/test'
import { appUrl } from './env'

test.describe('members tabs', () => {
  test('functions, applications and tiers are tabs, not sidebar rows', async ({ page }) => {
    await page.goto(appUrl('members'))
    await expect(page.getByRole('tab', { name: /^Mitglieder/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    for (const sub of ['functions', 'applications', 'tiers']) {
      await expect(page.locator(`a.nav-item[href$="/app/members/${sub}"]`)).toHaveCount(0)
    }
  })

  test('each tab opens its own address and keeps Members highlighted', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(appUrl('members'))

    const tabs: [RegExp, string][] = [
      [/^Funktionen/, 'functions'],
      [/^Anträge/, 'applications'],
      [/^Stufen/, 'tiers'],
    ]
    for (const [name, path] of tabs) {
      await page.getByRole('tab', { name }).click()
      await expect(page).toHaveURL(new RegExp(`/app/members/${path}$`))
      await expect(page.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true')
      await expect(page.locator('a.nav-item[href$="/app/members"]').first()).toHaveAttribute(
        'data-active',
        'true',
      )
      await expect(page.getByText('Etwas ist schiefgelaufen')).toHaveCount(0)
    }

    await page.getByRole('tab', { name: /^Mitglieder/ }).click()
    await expect(page).toHaveURL(/\/app\/members$/)
    expect(errors).toEqual([])
  })

  test('a tab address opens with that tab selected', async ({ page }) => {
    await page.goto(appUrl('members/tiers'))
    await expect(page.getByRole('tab', { name: /^Stufen/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })
})
