import { expect, test } from '@playwright/test'
import { appUrl } from './env'

const entry = (page: import('@playwright/test').Page, path: string) =>
  page.locator(`a.nav-item[href$="${path}"]`).first()

test.describe('members tabs', () => {
  test('statistics is a tab of Mitglieder: the same people, another view', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(appUrl('members'))
    await expect(page.getByRole('tab', { name: /^Mitglieder/ })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page.getByRole('tab', { name: /^Statistik/ }).click()
    await expect(page).toHaveURL(/\/app\/members\/stats$/)
    await expect(entry(page, '/app/members')).toHaveAttribute('data-active', 'true')
    await page.getByRole('tab', { name: /^Mitglieder/ }).click()
    await expect(page).toHaveURL(/\/app\/members$/)
    expect(errors).toEqual([])
  })

  test('functions, tiers and applications are pages with their own row', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(appUrl('members'))
    for (const name of [/^Funktionen/, /^Stufen/, /^Anträge/]) {
      await expect(page.getByRole('tab', { name })).toHaveCount(0)
    }

    const pages: [string, string][] = [
      ['Funktionen', 'functions'],
      ['Stufen', 'tiers'],
      ['Anträge', 'applications'],
    ]
    for (const [name, path] of pages) {
      await entry(page, `/app/members/${path}`).click()
      await expect(page).toHaveURL(new RegExp(`/app/members/${path}$`))
      await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
      await expect(entry(page, `/app/members/${path}`)).toHaveAttribute('data-active', 'true')
      await expect(entry(page, '/app/members')).not.toHaveAttribute('data-active', 'true')
      await expect(page.getByText('Etwas ist schiefgelaufen')).toHaveCount(0)
    }
    expect(errors).toEqual([])
  })
})
