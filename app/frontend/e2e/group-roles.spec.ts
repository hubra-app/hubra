import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

type Group = { id: number; role_ids: number[]; tier_ids: number[]; is_default: boolean }

test('a group gives roles, takes a tier and new members', async ({ page }) => {
  const role = await api<{ id: number; name: string }>(page, 'POST', '/roles/', {
    name: unique('E2E Werkstatt'),
  })
  const tiers = await api<{ id: number; name: string }[]>(page, 'GET', '/tiers/')
  const group = await api<Group>(page, 'POST', '/groups/', { name: unique('E2E Rollen') })
  try {
    await page.goto(appUrl(`groups/${group.id}`))
    await page.getByRole('button', { name: 'Bearbeiten' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByTestId('group-roles').click()
    await page.getByRole('option', { name: role.name }).click()
    await dialog.getByRole('heading').first().click()
    await dialog.getByTestId('group-tiers').click()
    await page.getByRole('option', { name: tiers[0].name }).click()
    await dialog.getByRole('heading').first().click()
    await dialog.getByRole('switch', { name: 'Neue Mitglieder kommen in diese Gruppe' }).check()
    await dialog.getByRole('button', { name: 'Speichern' }).click()
    await expect(dialog).toBeHidden()

    const saved = await api<Group>(page, 'GET', `/groups/${group.id}`)
    expect(saved.role_ids).toEqual([role.id])
    expect(saved.tier_ids).toEqual([tiers[0].id])
    expect(saved.is_default).toBe(true)
    await expect(page.getByText('Für neue Mitglieder')).toBeVisible()
    await expect(page.getByRole('main').getByText(role.name)).toBeVisible()

    // An open group gives no roles: the picker turns off.
    await page.getByRole('button', { name: 'Bearbeiten' }).click()
    await expect(page.getByRole('listbox')).toHaveCount(0)
    await page.getByRole('dialog').getByText('Offen', { exact: true }).click()
    await expect(page.getByRole('dialog').getByText(/Eine offene Gruppe gibt keine Rollen/)).toBeVisible()
  } finally {
    await api(page, 'DELETE', `/groups/${group.id}`)
    await api(page, 'DELETE', `/roles/${role.id}`)
  }
})

test('a group function is filled on the group page and counts there', async ({ page }) => {
  const group = await api<Group>(page, 'POST', '/groups/', { name: unique('E2E Team') })
  const fn = await api<{ id: number; name: string }>(page, 'POST', '/functions/', {
    name: unique('E2E Trainer/in'),
    perGroup: true,
  })
  try {
    await page.goto(appUrl(`members/functions/${fn.id}`))
    await expect(page.getByText('Gruppenfunktion').first()).toBeVisible()

    const members = await api<{ data: { id: number; name: string }[] }>(page, 'GET', '/members/?pageSize=1')
    const member = members.data[0]
    await api(page, 'POST', `/functions/${fn.id}/holders`, { memberId: member.id, groupId: group.id })

    await page.goto(appUrl(`groups/${group.id}`))
    await page.getByRole('tab', { name: 'Funktionen' }).click()
    const list = page.getByTestId('group-functions')
    await expect(list.getByText(fn.name)).toBeVisible()
    await expect(list.getByText(member.name)).toBeVisible()
    await list.getByRole('button', { name: 'Entfernen' }).click()
    await expect(list.getByText(fn.name)).toHaveCount(0)
  } finally {
    await api(page, 'DELETE', `/functions/${fn.id}`)
    await api(page, 'DELETE', `/groups/${group.id}`)
  }
})
