import { expect, test, type Page } from '@playwright/test'
import { appUrl } from './env'

const sidebar = (page: Page) => page.locator('.mantine-AppShell-navbar')
const entry = (page: Page, path: string) =>
  sidebar(page).locator(`a.nav-item[href$="${path}"]`)

async function openCustomize(page: Page) {
  // The user card at the foot of the sidebar opens the user menu.
  await sidebar(page).locator('button').last().click()
  await page.getByText('Seitenleiste anpassen').click()
  return page.getByRole('dialog', { name: 'Seitenleiste anpassen' })
}

async function resetSidebar(page: Page) {
  const dialog = await openCustomize(page)
  const reset = dialog.getByRole('button', { name: 'Zurücksetzen' })
  if (await reset.isEnabled()) await reset.click()
  await dialog.getByRole('button', { name: 'Fertig' }).click()
}

test.describe('settings tabs', () => {
  test('roles and the audit log are tabs of Einstellungen', async ({ page }) => {
    await page.goto(appUrl('settings'))
    await expect(entry(page, '/app/audit-log')).toHaveCount(0)
    await expect(entry(page, '/app/system')).toHaveCount(0)

    for (const [name, path] of [
      ['Rollen', '/app/system'],
      ['Protokoll', '/app/audit-log'],
    ]) {
      await page.getByRole('tab', { name }).click()
      await expect(page).toHaveURL(new RegExp(`${path}$`))
      await expect(page.getByRole('heading', { level: 1, name: 'Einstellungen' })).toBeVisible()
      await expect(page.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true')
      await expect(entry(page, '/app/settings')).toHaveAttribute('data-active', 'true')
    }
  })
})

test.describe('Weitere', () => {
  test('opens the first page behind it, with tabs for the others', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    await entry(page, '/app/more').click()
    await expect(page).not.toHaveURL(/\/app\/more$/)
    await expect(page.getByRole('tab').first()).toHaveAttribute('aria-selected', 'true')
    await expect(entry(page, '/app/more')).toHaveAttribute('data-active', 'true')
  })
})

test.describe('own sidebar', () => {
  test.afterEach(async ({ page }) => {
    await resetSidebar(page)
  })

  test('pinned entries move to Favoriten, hidden ones to Weitere', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    const dialog = await openCustomize(page)
    await dialog.getByRole('button', { name: 'Als Favorit anheften: Gruppen' }).click()
    await dialog.getByRole('button', { name: 'Ausblenden: Finanzen' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()

    await expect(sidebar(page).getByText('Favoriten')).toBeVisible()
    await expect(sidebar(page).locator('a.nav-item').first()).toHaveAttribute(
      'href',
      /\/app\/groups$/,
    )
    await expect(entry(page, '/app/finance')).toHaveCount(0)

    // Hidden, but one click away under Weitere and found by the search.
    await entry(page, '/app/more').click()
    await page.getByRole('tab', { name: 'Finanzen' }).click()
    await expect(page).toHaveURL(/\/app\/finance$/)
    await expect(entry(page, '/app/more')).toHaveAttribute('data-active', 'true')

    await page.goto(appUrl('dashboard'))
    await page.getByPlaceholder(/suchen/i).fill('Finanz')
    await page.getByText('Seite', { exact: true }).first().click()
    await expect(page).toHaveURL(/\/app\/finance$/)

    // Saved on the account: a reload keeps it.
    await page.reload()
    await expect(entry(page, '/app/finance')).toHaveCount(0)
  })
})
