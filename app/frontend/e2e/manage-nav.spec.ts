import { expect, test } from '@playwright/test'
import { MANAGE_URL } from './env'

// manage: the sidebar is grouped by what an operator does, each page's tabs
// are parts of one job, and every old URL still opens the right place.

test('manage groups the sidebar by task', async ({ page }) => {
  await page.goto(`${MANAGE_URL}/app/platform/alerts`)
  const nav = page.locator('nav, .mantine-AppShell-navbar').first()
  for (const section of ['Vereine', 'Betrieb', 'Dienste', 'Zugriff & Sicherheit']) {
    await expect(nav.getByText(section, { exact: true })).toBeVisible()
  }
  for (const entry of ['Alle Vereine', 'Warnungen', 'Diagnose', 'Wartung', 'Mail', 'Discord']) {
    await expect(nav.getByRole('link', { name: entry, exact: true })).toBeVisible()
  }
  // The old catch-all settings page is gone from the sidebar.
  await expect(nav.getByRole('link', { name: 'Einstellungen', exact: true })).toHaveCount(0)
})

test('a page tab is its own URL', async ({ page }) => {
  await page.goto(`${MANAGE_URL}/app/platform/mail`)
  await expect(page.getByRole('heading', { level: 1, name: 'Mail' })).toBeVisible()
  await page.getByRole('tab', { name: 'Einstellungen' }).click()
  await expect(page).toHaveURL(/\/app\/platform\/mail\/settings$/)
  await expect(page.getByRole('heading', { name: 'Mail-Relay' })).toBeVisible()
})

test('old manage URLs redirect to where the page lives now', async ({ page }) => {
  const cases: [string, RegExp][] = [
    ['/app/platform/settings', /\/app\/platform\/mail\/settings$/],
    ['/app/platform/settings/limits', /\/app\/tenants\/settings$/],
    ['/app/platform/settings/backups', /\/app\/platform\/backups\/settings$/],
    ['/app/platform/mail/relay', /\/app\/platform\/mail\/settings$/],
    ['/app/platform/discord/channels', /\/app\/platform\/discord\/settings$/],
    ['/app/platform/backups/storage', /\/app\/platform\/backups\/settings$/],
    ['/app/platform/diagnostics/outbound-mail?level=error', /\/app\/platform\/mail\?level=error$/],
    ['/app/platform/diagnostics/permissions', /\/app\/roles\/api$/],
    ['/app/platform/alerts/performance', /\/app\/platform\/diagnostics\/performance$/],
    ['/app/requests', /\/app\/tenants\/requests$/],
  ]
  for (const [from, to] of cases) {
    await page.goto(`${MANAGE_URL}${from}`)
    await expect(page).toHaveURL(to)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  }
})
