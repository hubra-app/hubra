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
    // The new role starts without permissions; open it and let it see the
    // first area.
    await page.getByRole('button', { name: new RegExp(`^${name}`) }).click()
    await expect(page.getByRole('main').getByText(name, { exact: true })).toHaveCount(2)
    await page
      .getByRole('tabpanel', { name: 'Darf' })
      .getByText('Ansehen', { exact: true })
      .first()
      .click()
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
