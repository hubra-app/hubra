import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

interface Ev {
  id: number
  title: string
  date: string
  series_id: number | null
}

test('a weekly training: series, attendance and overview', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  const title = unique('E2E Training')
  // A past series, so the overview (this year until today) shows it.
  const year = new Date().getFullYear()
  const first = await api<Ev>(page, 'POST', '/events/', {
    title,
    date: `${year}-01-06`,
    type: 'Workshop',
    recurrence: { until: `${year}-01-27`, weekdays: [], skip_dates: [`${year}-01-13`] },
  })
  try {
    const dates = (await api<Ev[]>(page, 'GET', `/events/?from=${year}-01-01&to=${year}-01-31`))
      .filter((e) => e.title === title)
      .map((e) => e.date)
    expect(dates).toEqual([`${year}-01-06`, `${year}-01-20`, `${year}-01-27`])

    // Sign the admin up (as organiser: the date is past) and mark them
    // present from the roll.
    const me = await api<{ id: number }>(page, 'GET', '/account/')
    await api(page, 'POST', `/events/${first.id}/register/${me.id}`, {})
    await page.locator('main').getByPlaceholder(/Suchen/).fill(title)
    const row = page.getByRole('row', { name: new RegExp(title) }).first()
    await row.getByRole('button', { name: 'Anwesenheit erfassen' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByRole('button', { name: 'Übrige anwesend' }).click()
    await dialog.getByRole('button', { name: 'Speichern' }).click()
    await expect(dialog).toBeHidden()

    await page.getByRole('button', { name: 'Anwesenheit', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Anwesenheit' })).toBeVisible()
    await expect(page.getByRole('button', { name: /CSV/ })).toBeEnabled()
    const overview = await api<{ events: { id: number; present: number }[] }>(
      page,
      'GET',
      `/events/attendance?from=${year}-01-01&to=${year}-01-31`,
    )
    expect(overview.events.find((e) => e.id === first.id)?.present).toBe(1)
  } finally {
    await api(page, 'DELETE', `/events/${first.id}?scope=following`)
  }
})
