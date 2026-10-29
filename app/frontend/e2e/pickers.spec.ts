import { expect, test } from '@playwright/test'
import { api } from './api'
import { appUrl } from './env'

test('the group lead picker finds a member by typing their name', async ({ page }) => {
  await page.goto(appUrl('groups'))
  const { data } = await api<{ data: { first_name: string; last_name: string }[] }>(
    page,
    'GET',
    '/members/?pageSize=50',
  )
  // Search by first and last name together, so pick a member who has both.
  const m = data.find((x) => x.first_name && x.last_name) ?? data[0]
  const name = `${m.first_name} ${m.last_name}`.trim()

  await page
    .getByRole('button', { name: /Gruppe (hinzufügen|erstellen)|Neue Gruppe/ })
    .first()
    .click()
  const lead = page.getByRole('dialog').getByRole('combobox', { name: 'Gruppenleitung' })
  await lead.fill(name)
  await page.getByRole('option', { name }).click()
  await expect(lead).toHaveValue(name)
})
