import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('an event opens on its own page from the list', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  const title = unique('E2E Anlass')
  const date = new Date(Date.now() + 3 * 86_400_000).toISOString().slice(0, 10)
  const ev = await api<{ id: number }>(page, 'POST', '/events/', {
    title,
    date,
    type: 'Social',
    description: 'Bitte Salat mitbringen.',
  })
  try {
    await page.reload()
    const card = page.getByTestId('event-card').filter({ hasText: title })
    await card.getByRole('link', { name: title }).click()
    await expect(page).toHaveURL(new RegExp(`/operations/events/${ev.id}$`))
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
    await expect(page.getByText('Bitte Salat mitbringen.')).toBeVisible()

    // Signing up on the page shows up in the organisers' list.
    await page.getByRole('button', { name: 'Teilnehmen' }).click()
    await expect(page.getByRole('button', { name: 'Abmelden' })).toBeVisible()
    await expect(page.getByTestId('event-registrations')).toContainText('Anmeldungen (1)')
  } finally {
    await api(page, 'DELETE', `/events/${ev.id}`)
  }
})
