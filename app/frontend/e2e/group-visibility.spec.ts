import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a group is open, visible or private, shown on its card and filterable', async ({ page }) => {
  const name = unique('E2E Privat')
  await page.goto(appUrl('groups'))
  await page.getByRole('main').getByRole('button', { name: 'Gruppe hinzufügen' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name der Gruppe').fill(name)
  // Sichtbar is the default; the hint follows the choice.
  await expect(dialog.getByText(/sehen die Gruppe und wer dabei ist/)).toBeVisible()
  await dialog.getByText('Privat', { exact: true }).click()
  await expect(dialog.getByText(/Nur die Mitglieder der Gruppe/)).toBeVisible()
  await dialog.getByRole('button', { name: 'Gruppe erstellen' }).click()
  await expect(dialog).toBeHidden()

  const groups = await api<{ id: number; name: string; visibility: string }[]>(page, 'GET', '/groups/')
  const created = groups.find((g) => g.name === name)
  expect(created?.visibility).toBe('private')
  try {
    const card = page.getByRole('main').locator('.mantine-Paper-root', { hasText: name }).last()
    await expect(card.getByText('Privat', { exact: true })).toBeVisible()

    const filter = page.getByRole('main').getByRole('radiogroup', { name: 'Sichtbarkeit' })
    await filter.getByText('Offen', { exact: true }).click()
    await expect(page.getByRole('main').getByText(name)).toHaveCount(0)
    await filter.getByText('Privat', { exact: true }).click()
    await expect(page.getByRole('main').getByText(name)).toBeVisible()

    await card.getByRole('button', { name: 'Bearbeiten' }).click()
    await page.getByRole('dialog').getByText('Offen', { exact: true }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Speichern' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()
    const saved = await api<{ visibility: string }>(page, 'GET', `/groups/${created!.id}`)
    expect(saved.visibility).toBe('open')
  } finally {
    await api(page, 'DELETE', `/groups/${created!.id}`)
  }
})
