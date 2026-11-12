import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { MANAGE_URL, appUrl } from './env'

// The newest release that has changes (an empty "Unreleased" is left out,
// like the dialog does): its items as [German title, English "for" mark].
// The German file follows the English one by position; only English has marks.
function newestRelease(): { title: string; forWho: string }[] {
  const read = (name: string) =>
    readFileSync(new URL(`../../backend/${name}`, import.meta.url), 'utf8').split(/^## \[/m).slice(1)
  const de = read('CHANGELOG.de.md')
  const en = read('CHANGELOG.md')
  for (let i = 0; i < de.length; i++) {
    const titles = [...de[i].matchAll(/^- \*\*([^*]+)\*\*/gm)].map((m) => m[1])
    if (!titles.length) continue
    const marks = [...en[i].matchAll(/^- \*\*.*$/gm)].map((m) => m[0].match(/<!-- for: ([^>]*?) -->/)?.[1] ?? '')
    return titles.map((title, n) => ({ title, forWho: marks[n] ?? '' }))
  }
  throw new Error('CHANGELOG.de.md has no release with changes')
}

// "Neuigkeiten": the newest release open, older versions folded, a roadmap tab.
test('what is new shows the latest release, older versions on demand and the roadmap', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  const sidebar = page.locator('.mantine-AppShell-navbar')
  await sidebar.getByTestId('user-card').click()
  await sidebar.getByTestId('user-menu').getByRole('button', { name: 'Neuigkeiten' }).click()

  const dialog = page.getByRole('dialog', { name: 'Neuigkeiten' })
  await expect(dialog.getByText('Frühere Versionen', { exact: true })).toBeVisible()
  // The newest release shows its first changes; the rest come with one click,
  // so the check does not depend on which entry is listed first.
  const showAll = dialog.getByRole('button', { name: /^Alle \d+ Änderungen zeigen$/ })
  if (await showAll.count()) await showAll.click()
  // The notes follow the page language (German here, from CHANGELOG.de.md).
  // Items for everyone show; Hubra's own staff items never reach the club app.
  const items = newestRelease()
  const forAll = items.find((i) => !i.forWho)
  if (forAll) await expect(dialog.getByText(forAll.title, { exact: true })).toBeVisible()
  const staff = items.find((i) => i.forWho.split(/,\s*/).includes('staff'))
  if (staff) await expect(dialog.getByText(staff.title, { exact: true })).toHaveCount(0)
  // Older versions are folded: a heading per version, its changes hidden until opened.
  const older = dialog.locator('.mantine-Accordion-item')
  expect(await older.count()).toBeGreaterThan(0)
  expect(await older.count()).toBeLessThanOrEqual(5)
  const first = older.first()
  await expect(first.locator('.mantine-Accordion-panel')).toBeHidden()
  await first.locator('.mantine-Accordion-control').click()
  await expect(first.locator('.mantine-Accordion-panel')).toBeVisible()

  await dialog.getByText('Roadmap', { exact: true }).click()
  await expect(dialog.getByText('Als Nächstes', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Erledigt', { exact: true })).toBeVisible()

  // Once read, the menu no longer marks it.
  await page.keyboard.press('Escape')
  await sidebar.getByTestId('user-card').click()
  await expect(sidebar.getByTestId('whats-new-unseen')).toHaveCount(0)
})

test('manage has the changelog and the roadmap', async ({ page }) => {
  await page.goto(`${MANAGE_URL}/app/whats-new`)
  await expect(page.getByRole('heading', { name: 'Neuigkeiten' })).toBeVisible()
  await expect(page.getByText('Frühere Versionen', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Roadmap' }).click()
  await expect(page).toHaveURL(/\/app\/whats-new\/roadmap$/)
  await expect(page.getByText('Als Nächstes', { exact: true })).toBeVisible()
})
