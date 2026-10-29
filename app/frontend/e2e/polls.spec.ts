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
    // The list is a Paper too: the card is the innermost match.
    const card = page.locator('.mantine-Paper-root', { hasText: question }).last()
    await card.getByRole('button', { name: /^Nein/ }).click()
    await expect(card.getByText('Abgestimmt')).toBeVisible()

    await page.reload()
    await expect(card.getByText('Abgestimmt')).toBeVisible()
    await expect(card.getByRole('button', { name: /^Nein ✓/ })).toBeVisible()
  } finally {
    await api(page, 'DELETE', `/polls/${poll.id}`)
  }
})
