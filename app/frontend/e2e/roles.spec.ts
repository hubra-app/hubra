import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a new role can be created, given a permission and deleted', async ({ page }) => {
  const name = unique('E2E Rolle')
  await page.goto(appUrl('system/roles'))
  await page.getByRole('button', { name: 'Neue Rolle' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name der Rolle').fill(name)
  await dialog.getByLabel('Name der Rolle').press('Enter')
  await expect(dialog).toBeHidden()

  const roles = await api<{ id: number; name: string }[]>(page, 'GET', '/roles/')
  const role = roles.find((r) => r.name === name)
  expect(role).toBeTruthy()
  try {
    // The new role starts without permissions; tick the first one it shows.
    await page.getByRole('textbox', { name: 'Rollen' }).click()
    await page.getByRole('option', { name }).click()
    await page.keyboard.press('Escape')
    const column = page.locator('th', { hasText: name })
    await expect(column).toBeVisible()
    const index = await column.evaluate((th) => Array.from(th.parentElement!.children).indexOf(th))
    const box = page.locator(`tbody tr td:nth-child(${index + 1}) input[type=checkbox]`).first()
    await box.check()
    await expect
      .poll(
        async () =>
          (await api<{ permissions: string[] }>(page, 'GET', `/roles/${role!.id}/permissions`))
            .permissions.length,
      )
      .toBeGreaterThan(0)
  } finally {
    await api(page, 'DELETE', `/roles/${role!.id}`)
  }
})
