import { expect, test } from '@playwright/test'
import { api } from './api'
import { appUrl } from './env'

type Role = { id: number; name: string }
type Fn = { id: number; name: string; key: string | null; grantsRoleIds: number[] }

// docs/roles.md: every club has Vorstand and Aktuar/in next to Mitglied and
// Kassier/in, and the board functions give their roles.
test('the board functions give Vorstand and their own role', async ({ page }) => {
  const roles = await api<Role[]>(page, 'GET', '/roles/')
  const id = (name: string) => roles.find((r) => r.name === name)?.id
  expect(id('Board')).toBeTruthy()
  expect(id('Secretary')).toBeTruthy()

  const fns = await api<Fn[]>(page, 'GET', '/functions/')
  const kassier = fns.find((f) => f.key === 'treasurer')!
  expect(kassier.grantsRoleIds.sort()).toEqual([id('Board'), id('Treasurer')].sort())

  await page.goto(appUrl('members/functions'))
  await expect(page.getByText(/Gibt die Rollen .*Vorstand/).first()).toBeVisible()
})

test('Keine on a module hides it for the role', async ({ page }) => {
  const roles = await api<Role[]>(page, 'GET', '/roles/')
  const board = roles.find((r) => r.name === 'Board')!
  const perms = async () =>
    (await api<{ permissions: string[] }>(page, 'GET', `/roles/${board.id}/permissions`))
      .permissions
  const before = await perms()
  expect(before).toContain('module.finance.access')

  try {
    await page.goto(appUrl('system/roles'))
    await page.getByRole('button', { name: /^Vorstand/ }).click()
    const panel = page.getByRole('tabpanel', { name: 'Darf' })
    const finance = panel.getByRole('radiogroup', { name: 'Finanzen' }).first()
    await finance.getByText('Keine', { exact: true }).click()
    await expect.poll(perms).not.toContain('module.finance.access')
    await expect(panel.getByText('Ausgeblendet').first()).toBeVisible()

    await finance.getByText('Ansehen', { exact: true }).click()
    await expect.poll(perms).toContain('module.finance.access')
  } finally {
    await api(page, 'PUT', `/roles/${board.id}/permissions`, { permissions: before })
  }
})
