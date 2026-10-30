import { expect, test } from '@playwright/test'
import { api } from './api'
import { appUrl } from './env'

type ClubSettings = { club_name?: string; invite_valid_days?: number }
type Module = { code: string; config: Record<string, unknown> }

const tabNames = async (page: import('@playwright/test').Page) =>
  (await page.getByRole('tab').allInnerTexts()).map((s) => s.trim())

test('finance tabs put the daily work first and the settings last', async ({ page }) => {
  await page.goto(appUrl('finance'))
  await expect(page.getByRole('tab', { name: 'Übersicht' })).toBeVisible()
  const names = await tabNames(page)
  expect(names[0]).toBe('Übersicht')
  expect(names.indexOf('Rechnungen')).toBeLessThan(names.indexOf('Einnahmen und Ausgaben'))
  expect(names.indexOf('Einnahmen und Ausgaben')).toBeLessThan(names.indexOf('Kategorien'))
  expect(names.at(-1)).toBe('Einstellungen')
})

test('the payment term is set under Finanzen › Einstellungen', async ({ page }) => {
  await page.goto(appUrl('finance'))
  const before = (await api<Module[]>(page, 'GET', '/modules/')).find((m) => m.code === 'finance')!
  await page.getByRole('tab', { name: 'Einstellungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/settings$/)

  const term = page.getByLabel('Zahlungsfrist (Tage)')
  await term.fill('21')
  await page.getByRole('button', { name: 'Speichern' }).click()
  await expect(page.getByText('Einstellungen gespeichert').first()).toBeVisible()
  try {
    await page.reload()
    await expect(page.getByLabel('Zahlungsfrist (Tage)')).toHaveValue('21')
  } finally {
    await api(page, 'PUT', '/modules/finance/settings', { config: before.config })
  }

  // The bank account stays in the club settings; the finance tab links there.
  await page.getByRole('button', { name: 'Bankangaben öffnen' }).click()
  await expect(page).toHaveURL(/\/app\/settings\/bank$/)
  await expect(page.getByLabel('IBAN oder QR-IBAN')).toBeVisible()
})

test('club settings are split into Verein, Mitgliedschaft and Bank tabs', async ({ page }) => {
  await page.goto(appUrl('settings'))
  await expect(page.getByRole('heading', { name: 'Vereinsprofil' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ankündigungsbanner' })).toBeVisible()
  await expect(page.getByLabel('IBAN oder QR-IBAN')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Privatsphäre' })).toHaveCount(0)
  const names = await tabNames(page)
  expect(names.slice(0, 3)).toEqual(['Verein', 'Mitgliedschaft', 'Bank & QR-Rechnung'])

  await page.getByRole('tab', { name: 'Bank & QR-Rechnung' }).click()
  await expect(page).toHaveURL(/\/app\/settings\/bank$/)
  await expect(page.getByLabel('IBAN oder QR-IBAN')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Vereinsprofil' })).toHaveCount(0)
})

test('saving the membership tab keeps what the Verein tab holds', async ({ page }) => {
  await page.goto(appUrl('settings/membership'))
  const before = (await api<{ settings: ClubSettings }>(page, 'GET', '/admin/club-settings'))
    .settings
  await expect(page.getByRole('heading', { name: 'Privatsphäre' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Vereinsprofil' })).toHaveCount(0)

  const days = before.invite_valid_days === 9 ? '10' : '9'
  await page.getByLabel('Einladungen gültig (Tage)').fill(days)
  await page.getByRole('button', { name: 'Einstellungen speichern' }).click()
  await expect(page.getByText('Einstellungen gespeichert').first()).toBeVisible()
  try {
    const after = (await api<{ settings: ClubSettings }>(page, 'GET', '/admin/club-settings'))
      .settings
    expect(after.invite_valid_days).toBe(Number(days))
    expect(after.club_name).toBe(before.club_name)

    // The Verein tab shows the saved state, not what it loaded earlier.
    await page.getByRole('tab', { name: 'Verein' }).click()
    await expect(page.getByLabel('Vereinsname')).toHaveValue(before.club_name ?? '')
  } finally {
    // null takes the field away again if the club had not set it.
    await api(page, 'PATCH', '/admin/club-settings', {
      invite_valid_days: before.invite_valid_days ?? null,
    })
  }
})
