import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

type Recurring = { id: number; description: string; next_date: string | null; yearly_amount: number }

test('a recurring expense is entered once and shows what it costs a year', async ({ page }) => {
  const name = unique('Hallenmiete')
  await page.goto(appUrl('finance/recurring'))
  await page.getByRole('button', { name: 'Neue wiederkehrende Buchung' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Beschreibung').fill(name)
  await dialog.getByLabel('Betrag (CHF)').fill('250')
  await dialog.getByRole('combobox', { name: 'Wiederholung' }).click()
  await page.getByRole('option', { name: 'Vierteljährlich', exact: true }).click()
  await dialog.getByRole('button', { name: 'Erstellen' }).click()

  const row = page.getByRole('row', { name: new RegExp(name) })
  await expect(row).toContainText('Vierteljährlich')
  await expect(row).toContainText(/1.000\.00/)

  const created = (await api<Recurring[]>(page, 'GET', '/finance/recurring')).find(
    (r) => r.description === name,
  )!
  expect(created.yearly_amount).toBe(1000)
  expect(created.next_date).not.toBeNull()

  // Paused, it stays in the list without a next date.
  await row.getByRole('button', { name: 'Bearbeiten' }).click()
  await dialog.getByRole('switch', { name: 'Aktiv' }).click({ force: true })
  await dialog.getByRole('button', { name: 'Speichern' }).click()
  await expect(row).toContainText('Pausiert')

  await api(page, 'DELETE', `/finance/recurring/${created.id}`)
})
