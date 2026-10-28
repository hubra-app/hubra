import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('an inventory item can be added, opened and edited', async ({ page }) => {
  const name = unique('E2E Bohrer')
  await page.goto(appUrl('inventory'))
  await page.getByRole('button', { name: 'Gegenstand hinzufügen' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill(name)
  await dialog.getByLabel('Name').press('Enter')
  await expect(dialog).toBeHidden()

  const items = await api<{ id: number; name: string }[]>(page, 'GET', '/inventory/')
  const item = items.find((i) => i.name === name)
  expect(item).toBeTruthy()
  try {
    await page.getByRole('main').getByText(name).first().click()
    const panel = page.getByRole('dialog', { name })
    await expect(panel).toBeVisible()
    await panel.getByRole('button', { name: 'Schliessen' }).click()

    await page
      .getByRole('main')
      .locator('.mantine-Paper-root', { hasText: name })
      .last()
      .getByRole('button', { name: 'Bearbeiten' })
      .click()
    const form = page.getByRole('dialog')
    await expect(form.getByLabel('Name')).toHaveValue(name)
    await form.getByLabel('Kosten (CHF, optional)').fill('12.50')
    await form.getByRole('button', { name: 'Änderungen speichern' }).click()
    await expect(form).toBeHidden()
    const saved = await api<{ cost: string | null }>(page, 'GET', `/inventory/${item!.id}`)
    expect(Number(saved.cost)).toBe(12.5)
  } finally {
    await api(page, 'DELETE', `/inventory/${item!.id}`)
  }
})
