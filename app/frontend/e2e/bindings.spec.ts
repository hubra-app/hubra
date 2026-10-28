import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a binding can be added and edited', async ({ page }) => {
  await page.goto(appUrl('operations/bindings/list'))
  const keyName = unique('e2e.key').replace(/\s/g, '_')
  const key = await api<{ id: number }>(page, 'POST', '/bindings/keys', { key: keyName })
  try {
    await page.reload()
    await page.getByRole('button', { name: 'Verknüpfung hinzufügen' }).click()
    const dialog = page.getByRole('dialog')
    const pick = async (label: string, option?: string) => {
      await dialog.getByRole('combobox', { name: label }).click()
      const opts = page.getByRole('option')
      await (option ? opts.filter({ hasText: option }) : opts.nth(1)).first().click()
    }
    await pick('Quelle')
    await pick('Attribut')
    await pick('Zielschlüssel', keyName)
    await dialog.getByRole('button', { name: 'Speichern' }).click()
    await expect(dialog).toBeHidden()

    const bindings = await api<{ id: number; key_id: number }[]>(
      page,
      'GET',
      `/bindings/?key_id=${key.id}`,
    )
    expect(bindings).toHaveLength(1)

    await page
      .getByRole('row', { name: new RegExp(keyName) })
      .getByRole('button', { name: /bearbeiten|Edit/i })
      .first()
      .click()
    await expect(
      page.getByRole('dialog').getByRole('combobox', { name: 'Zielschlüssel' }),
    ).toHaveValue(new RegExp(keyName))
    await page.getByRole('dialog').getByRole('checkbox').check()
    await page.getByRole('dialog').getByRole('button', { name: 'Speichern' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()
    const after = await api<{ is_protected: boolean }[]>(page, 'GET', `/bindings/?key_id=${key.id}`)
    expect(after[0].is_protected).toBe(true)
  } finally {
    for (const b of await api<{ id: number }[]>(page, 'GET', `/bindings/?key_id=${key.id}`)) {
      await api(page, 'PUT', `/bindings/${b.id}`, { is_protected: false })
      await api(page, 'DELETE', `/bindings/${b.id}`)
    }
    await api(page, 'DELETE', `/bindings/keys/${key.id}`)
  }
})
