import { expect, test, type Locator, type Page } from '@playwright/test'
import { api, enableModule, unique } from './api'
import { appUrl } from './env'

// Edit dialogs follow the member form: a wide dialog with paired fields
// side by side, one column on phones.
const DIALOGS = [
  { path: 'groups', button: 'Gruppe hinzufügen', pair: ['Name der Gruppe', 'Gruppenleitung'] },
  { path: 'members/functions', button: 'Hinzufügen', pair: ['Name', 'Max. Anzahl Personen'] },
  { path: 'members/tiers', button: 'Neue Stufe', pair: ['Abrechnung', 'Preis (CHF)'] },
  { path: 'operations/events', module: 'events', button: 'Anlass hinzufügen', pair: ['Datum', 'Zeit (optional)'] },
  { path: 'inventory', module: 'inventory', button: 'Gegenstand hinzufügen', pair: ['Kategorie', 'Status'] },
  { path: 'finance/external-parties', button: 'Neue Partei', pair: ['Name', 'E-Mail'] },
  { path: 'finance/invoices', button: 'Rechnung ausstellen', pair: ['Empfängertyp', 'Mitglied'] },
]

async function openDialog(page: Page, path: string, button: string) {
  await page.goto(appUrl(path))
  await page.getByRole('main').getByRole('button', { name: button }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  return dialog
}

const field = (dialog: Locator, label: string) => dialog.getByLabel(label, { exact: true }).first()

for (const d of DIALOGS) {
  test(`the ${d.path} dialog pairs fields when wide and stacks them on a phone`, async ({ page }) => {
    if (d.module) {
      await page.goto(appUrl('dashboard'))
      await enableModule(page, d.module)
    }
    let dialog = await openDialog(page, d.path, d.button)
    const box = await page.locator('.mantine-Modal-content').boundingBox()
    expect(box!.width).toBeGreaterThan(560)
    let [a, b] = [await field(dialog, d.pair[0]).boundingBox(), await field(dialog, d.pair[1]).boundingBox()]
    expect(Math.abs(a!.y - b!.y)).toBeLessThan(10)
    expect(b!.x).toBeGreaterThan(a!.x + a!.width)
    await expect(dialog.locator('input:disabled')).toHaveCount(0)

    await page.setViewportSize({ width: 390, height: 844 })
    dialog = await openDialog(page, d.path, d.button)
    ;[a, b] = [await field(dialog, d.pair[0]).boundingBox(), await field(dialog, d.pair[1]).boundingBox()]
    expect(b!.y).toBeGreaterThan(a!.y + a!.height)
    const overflow = await page
      .locator('.mantine-Modal-body')
      .evaluate((el) => el.scrollWidth - el.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
}

test('editing an active code shows it as active', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  await enableModule(page, 'codes')
  const name = unique('E2E Code')
  const code = await api<{ id: number }>(page, 'POST', '/codes/', { name, code: '4711' })
  try {
    await page.goto(appUrl('operations/codes'))
    await page
      .getByRole('main')
      .locator('tr, .mantine-Paper-root', { hasText: name })
      .last()
      .getByRole('button', { name: 'Bearbeiten' })
      .click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByText(name)).toBeVisible()
    await expect(dialog.getByRole('checkbox', { name: 'Aktiv' })).toBeChecked()
  } finally {
    await api(page, 'DELETE', `/codes/${code.id}`)
  }
})

test('a system role keeps its name out of the edit form', async ({ page }) => {
  await page.goto(appUrl('system/roles'))
  // The built-in member role: a system role that may be edited.
  await page.getByRole('main').getByRole('button', { name: /^Mitglied \d/ }).click()
  await page.getByRole('button', { name: 'Rolle bearbeiten' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Mitglied · Systemrolle')).toBeVisible()
  await expect(dialog.getByLabel('Name der Rolle')).toHaveCount(0)
  await expect(dialog.locator('input:disabled')).toHaveCount(0)
  await expect(dialog.getByLabel('Beschreibung')).toBeEditable()
})
