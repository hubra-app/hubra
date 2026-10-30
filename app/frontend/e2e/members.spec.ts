import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { EMAIL, appUrl } from './env'

type BackendMember = { id: number; email: string | null; notes: string | null }

test('editing a member shows only what the club can change, in a wide dialog', async ({ page }) => {
  await page.goto(appUrl('members'))
  const { data } = await api<{ data: BackendMember[] }>(
    page,
    'GET',
    `/members?search=${encodeURIComponent(EMAIL)}`,
  )
  const me = data.find((m) => m.email === EMAIL)
  expect(me).toBeTruthy()

  await page.goto(appUrl(`members/${me!.id}`))
  await page.getByRole('button', { name: 'Bearbeiten' }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Mitglied bearbeiten')).toBeVisible()

  // Name and email belong to the member's own account: in the subtitle,
  // never as greyed-out fields.
  await expect(dialog.getByText(EMAIL)).toBeVisible()
  await expect(dialog.getByLabel('Private E-Mail')).toHaveCount(0)
  await expect(dialog.getByLabel('Vorname')).toHaveCount(0)
  await expect(dialog.getByLabel('Nachname')).toHaveCount(0)
  await expect(dialog.locator('input:disabled')).toHaveCount(0)
  await expect(dialog.getByLabel('Status')).toBeVisible()
  await expect(dialog.getByLabel('Rollen')).toBeVisible()

  const box = await page.locator('.mantine-Modal-content').boundingBox()
  expect(box!.width).toBeGreaterThan(560)

  const note = unique('E2E Notiz')
  await dialog.getByLabel('Notizen').fill(note)
  await dialog.getByRole('button', { name: 'Änderungen speichern' }).click()
  await expect(dialog).toBeHidden()
  const saved = await api<BackendMember>(page, 'GET', `/members/${me!.id}`)
  expect(saved.notes).toBe(note)
  await api(page, 'PATCH', `/members/${me!.id}`, { notes: me!.notes ?? '' })
})

test('the invite dialog still asks for email and name', async ({ page }) => {
  await page.goto(appUrl('members?invite=1'))
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Private E-Mail')).toBeEditable()
  await expect(dialog.getByLabel('Vorname')).toBeEditable()
  await expect(dialog.getByLabel('Nachname')).toBeEditable()
  await dialog.getByRole('button', { name: 'Abbrechen' }).click()
  await expect(dialog).toBeHidden()
})
