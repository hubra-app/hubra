import { expect, test, type Page } from '@playwright/test'
import { api, enableModule, unique } from './api'
import { appUrl } from './env'

// Groups, functions, tiers and audit entries open as their
// own pages (like a member), not in a side panel: a deep link works, the
// back link returns to the list, and the edit dialog opens from the page.

const main = (page: Page) => page.getByRole('main')

test('a group opens as its own page with members, edit and back', async ({ page }) => {
  await page.goto(appUrl('groups'))
  await enableModule(page, 'groups')
  const name = unique('E2E Gruppe')
  const group = await api<{ id: number }>(page, 'POST', '/groups/', { name, description: 'Mittwochs' })
  try {
    await page.goto(appUrl('groups'))
    await main(page).getByRole('button', { name, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/app/groups/${group.id}$`))
    await expect(main(page).getByRole('heading', { level: 1, name })).toBeVisible()
    await expect(page.getByTestId('group-members')).toBeVisible()
    // No side panel any more.
    await expect(page.locator('.mantine-Drawer-content')).toHaveCount(0)

    await main(page).getByRole('button', { name: 'Bearbeiten' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByLabel('Name der Gruppe')).toHaveValue(name)
    await dialog.getByRole('button', { name: 'Abbrechen' }).click()
    await expect(dialog).toBeHidden()

    // A deep link opens the same page; the back link returns to the list.
    await page.goto(appUrl(`groups/${group.id}`))
    await expect(main(page).getByRole('heading', { level: 1, name })).toBeVisible()
    await page.getByTestId('detail-back').click()
    await expect(page).toHaveURL(/\/app\/groups$/)
  } finally {
    await api(page, 'DELETE', `/groups/${group.id}`)
  }
})

test('a function and a tier open as their own pages', async ({ page }) => {
  await page.goto(appUrl('members/functions'))
  await enableModule(page, 'functions')
  const fnName = unique('E2E Amt')
  const fn = await api<{ id: number }>(page, 'POST', '/functions/', { name: fnName, maxHolders: 2 })
  const tierName = unique('E2E Stufe')
  const tier = await api<{ id: number }>(page, 'POST', '/tiers/', {
    name: tierName,
    color: '#7441e0',
    price_type: 'fixed',
    price_chf: 30,
  })
  try {
    await page.goto(appUrl('members/functions'))
    await main(page).getByText(fnName, { exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/app/members/functions/${fn.id}$`))
    await expect(page.getByTestId('function-holder-count')).toHaveText('0 / 2')
    await expect(page.getByTestId('function-holders')).toBeVisible()

    await page.goto(appUrl('members/tiers'))
    await main(page).getByRole('button', { name: tierName, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/app/members/tiers/${tier.id}$`))
    await expect(page.getByTestId('tier-members')).toBeVisible()
    await main(page).getByRole('button', { name: 'Bearbeiten' }).click()
    await expect(page.getByRole('dialog').getByLabel('Name der Stufe')).toHaveValue(tierName)
  } finally {
    await api(page, 'DELETE', `/functions/${fn.id}`)
    await api(page, 'DELETE', `/tiers/${tier.id}`)
  }
})

test('an audit entry opens as its own page and links to its record', async ({ page }) => {
  await page.goto(appUrl('groups'))
  await enableModule(page, 'groups')
  const name = unique('E2E Protokoll')
  const group = await api<{ id: number }>(page, 'POST', '/groups/', { name })
  try {
    const log = await api<{ data: { id: number; target_label: string }[] }>(
      page,
      'GET',
      `/audit/?targetType=Group&targetId=${group.id}`,
    )
    const entry = log.data[0]
    expect(entry.target_label).toBe(name)
    await page.goto(appUrl(`audit-log/${entry.id}`))
    await expect(main(page).getByRole('heading', { level: 1 })).toBeVisible()
    await page.getByTestId('audit-target-link').click()
    await expect(page).toHaveURL(new RegExp(`/app/groups/${group.id}$`))
    // The group's activity tab lists the same entry.
    await main(page).getByRole('tab', { name: 'Aktivität' }).click()
    await expect(page.getByTestId('group-activity')).toContainText(name)
  } finally {
    await api(page, 'DELETE', `/groups/${group.id}`)
  }
})
