import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a vote is still shown after the page reloads', async ({ page }) => {
  await page.goto(appUrl('operations/polls'))
  const question = unique('E2E Umfrage')
  const poll = await api<{ id: number }>(page, 'POST', '/polls/', {
    question,
    options: [{ label: 'Ja' }, { label: 'Nein' }],
  })
  try {
    await page.reload()
    const card = page.getByTestId('poll-card').filter({ hasText: question })
    await card.getByRole('button', { name: 'Nein' }).click()
    await expect(card.getByText('Abgestimmt')).toBeVisible()

    await page.reload()
    await expect(card.getByText('Abgestimmt')).toBeVisible()
    await expect(card.getByLabel('Deine Stimme')).toBeVisible()
    // The vote can be changed while the poll is open.
    await card.getByTestId('change-vote').click()
    await card.getByRole('button', { name: 'Ja' }).click()
    await expect(card.locator('p', { hasText: /^Ja$/ }).getByLabel('Deine Stimme')).toBeVisible()
  } finally {
    await api(page, 'DELETE', `/polls/${poll.id}`)
  }
})
