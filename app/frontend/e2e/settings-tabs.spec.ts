import { expect, test } from '@playwright/test'
import { api } from './api'
import { appUrl } from './env'

type ClubSettings = { club_name?: string; invite_valid_days?: number }
type Module = { code: string; config: Record<string, unknown> }

const tabNames = async (page: import('@playwright/test').Page, row?: string) => {
  const scope = row ? page.getByRole('tablist', { name: row, exact: true }) : page
  await expect(scope.getByRole('tab').first()).toBeVisible()
  return (await scope.getByRole('tab').allInnerTexts()).map((s) => s.trim())
}

test('finance has five page tabs, with sub-tabs where a topic has several lists', async ({
  page,
}) => {
  await page.goto(appUrl('finance'))
  await expect(page.getByRole('tab', { name: 'Übersicht' })).toBeVisible()
  const names = await tabNames(page, 'Finanzen')
  expect(names.slice(0, 3)).toEqual(['Übersicht', 'Rechnungen', 'Buchungen'])
  // "Budget & Beiträge" with the budgets plugin, else just the fee basis.
  expect(['Budget & Beiträge', 'Beitragsgrundlage']).toContain(names[3])
  expect(names.at(-1)).toBe('Einstellungen')
  // The overview has no second row.
  await expect(page.getByRole('tablist')).toHaveCount(1)

  await page.getByRole('tab', { name: 'Buchungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/transactions$/)
  const bookings = await tabNames(page, 'Buchungen')
  expect(bookings.slice(0, 2)).toEqual(['Einnahmen und Ausgaben', 'Wiederkehrend'])
  await page.getByRole('tab', { name: 'Wiederkehrend' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/recurring$/)
  await expect(page.getByRole('tab', { name: 'Buchungen' })).toHaveAttribute('aria-selected', 'true')

  await page.getByRole('tab', { name: 'Einstellungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/settings$/)
  expect(await tabNames(page, 'Einstellungen')).toEqual([
    'Abrechnung',
    'Kategorien',
    'Externe Parteien',
    'Bank & QR-Rechnung',
  ])
})

test('old finance addresses open their page under the new tab', async ({ page }) => {
  for (const [path, tab, sub] of [
    ['finance/categories', 'Einstellungen', 'Kategorien'],
    ['finance/external-parties', 'Einstellungen', 'Externe Parteien'],
    ['finance/recurring', 'Buchungen', 'Wiederkehrend'],
  ] as const) {
    await page.goto(appUrl(path))
    await expect(page.getByRole('tab', { name: tab, exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await expect(page.getByRole('tab', { name: sub, exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  }
})

test('the payment term is set under Finanzen › Einstellungen', async ({ page }) => {
  await page.goto(appUrl('finance'))
  const before = (await api<Module[]>(page, 'GET', '/modules/')).find((m) => m.code === 'finance')!
  await page.getByRole('tab', { name: 'Einstellungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/settings$/)

  const term = page.getByLabel('Zahlungsfrist (Tage)')
  await term.fill('21')
  const invoiceCard = page
    .locator('.mantine-Paper-root')
    .filter({ has: page.getByRole('heading', { name: 'Rechnungen und Mahnungen' }) })
  await invoiceCard.getByRole('button', { name: 'Speichern' }).click()
  await expect(page.getByText('Einstellungen gespeichert').first()).toBeVisible()
  try {
    await page.reload()
    await expect(page.getByLabel('Zahlungsfrist (Tage)')).toHaveValue('21')
  } finally {
    await api(page, 'PUT', '/modules/finance/settings', { config: before.config })
  }

  // The bank account sits next to the billing rules.
  await page.getByRole('tab', { name: 'Bank & QR-Rechnung' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/bank-account$/)
  await expect(page.getByLabel('IBAN oder QR-IBAN')).toBeVisible()
})

test('membership fees are billed on a fixed date or the join date', async ({ page }) => {
  await page.goto(appUrl('finance/settings'))
  const before = (await api<Module[]>(page, 'GET', '/modules/')).find((m) => m.code === 'finance')!
  const card = page
    .locator('.mantine-Paper-root')
    .filter({ has: page.getByRole('heading', { name: 'Mitgliederbeiträge' }) })
  try {
    await card.getByLabel('Tag', { exact: true }).fill('15')
    await card.getByRole('switch', { name: /Ersten Beitrag kürzen/ }).click({ force: true })
    await card.getByRole('button', { name: 'Speichern' }).click()
    await expect(page.getByText('Einstellungen gespeichert').first()).toBeVisible()
    const after = (await api<Module[]>(page, 'GET', '/modules/')).find((m) => m.code === 'finance')!
    expect(after.config).toMatchObject({
      fee_anchor_day: 15,
      prorate_first_fee: !(before.config.prorate_first_fee ?? true),
      bill_on_join_date: false,
      // The other card's settings are kept.
      payment_term_days: before.config.payment_term_days ?? 30,
    })

    await card.getByText('Am Eintrittsdatum', { exact: true }).click()
    await expect(card.getByLabel('Tag', { exact: true })).toBeHidden()
    await card.getByRole('button', { name: 'Speichern' }).click()
    await expect
      .poll(async () => (await api<Module[]>(page, 'GET', '/modules/')).find((m) => m.code === 'finance')!.config.bill_on_join_date)
      .toBe(true)
  } finally {
    await api(page, 'PUT', '/modules/finance/settings', { config: before.config })
  }
})

test('club settings are split into Verein and Mitgliedschaft; the bank is under Finanzen', async ({
  page,
}) => {
  await page.goto(appUrl('settings'))
  await expect(page.getByRole('heading', { name: 'Vereinsprofil' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ankündigungsbanner' })).toBeVisible()
  await expect(page.getByLabel('IBAN oder QR-IBAN')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Privatsphäre' })).toHaveCount(0)
  const names = await tabNames(page)
  expect(names.slice(0, 2)).toEqual(['Verein', 'Mitgliedschaft'])
  expect(names).not.toContain('Bank & QR-Rechnung')

  // The finance module is on in the test club, so the old address moves on.
  await page.goto(appUrl('settings/bank'))
  await expect(page).toHaveURL(/\/app\/finance\/bank-account$/)
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

test('every settings tab has its own address', async ({ page }) => {
  // settings/apps had no route and fell through to the dashboard.
  for (const [path, tab] of [
    ['settings/membership', 'Mitgliedschaft'],
    ['settings/modules', 'Module'],
    ['settings/apps', 'Verbundene Apps'],
    ['settings/domains', 'Domains'],
  ] as const) {
    await page.goto(appUrl(path))
    await expect(page).toHaveURL(new RegExp(`/app/${path}$`))
    await expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true')
  }
})
