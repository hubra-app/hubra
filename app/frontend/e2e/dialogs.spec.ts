import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('Enter in a dialog field submits the dialog', async ({ page }) => {
  const name = unique('E2E Gruppe')
  await page.goto(appUrl('groups'))
  await page.getByRole('button', { name: /Gruppe (hinzufügen|erstellen)|Neue Gruppe/ }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel(/Gruppenname|Name/).first().fill(name)
  await dialog.getByLabel(/Gruppenname|Name/).first().press('Enter')
  await expect(dialog).toBeHidden()
  await expect(page.getByText(name).first()).toBeVisible()

  const groups = await api<{ id: number; name: string }[]>(page, 'GET', '/groups/')
  const created = groups.find((g) => g.name === name)
  expect(created).toBeTruthy()
  await api(page, 'DELETE', `/groups/${created!.id}`)
})
