import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

interface Ev {
  id: number
  title: string
}

const inDays = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

test('an event has its own page: details, sign-up and who is coming', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  const title = unique('E2E Grillabend')
  const ev = await api<Ev>(page, 'POST', '/events/', {
    title,
    date: inDays(3),
    time: '18:00',
    location: 'Garten',
    type: 'Social',
    description: 'Bring etwas zum Grillieren mit.',
  })
  try {
    await page.locator('main').getByPlaceholder(/Suchen/).fill(title)
    await page.getByTestId('event-title').filter({ hasText: title }).click()
    await expect(page).toHaveURL(new RegExp(`operations/events/${ev.id}$`))
    const detail = page.getByTestId('event-detail')
    await expect(detail.getByRole('heading', { name: title })).toBeVisible()
    await expect(detail.getByText('Bring etwas zum Grillieren mit.')).toBeVisible()
    await expect(detail.getByTestId('event-participants')).toContainText('Noch niemand angemeldet')

    await detail.getByTestId('event-join').click()
    await expect(detail.getByTestId('event-join')).toHaveText(/Abmelden/)
    await expect(detail.getByTestId('event-participants')).not.toContainText('Noch niemand angemeldet')

    await detail.getByTestId('detail-back').click()
    await expect(page).toHaveURL(/operations\/events$/)
  } finally {
    await api(page, 'DELETE', `/events/${ev.id}`)
  }
})

test('Anlässe shows a month and its tabs', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  await expect(page.getByRole('tab', { name: 'Anlässe' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Anwesenheit' })).toBeVisible()
  await page.getByTestId('events-view').locator('label', { hasText: 'Monat' }).click()
  await expect(page.getByTestId('events-month')).toBeVisible()
  // Back to the list for the other tests on this device.
  await page.getByTestId('events-view').locator('label', { hasText: 'Liste' }).click()
  await expect(page.getByTestId('events-month')).toBeHidden()
})
