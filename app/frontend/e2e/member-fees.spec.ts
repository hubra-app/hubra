import { expect, test } from '@playwright/test'
import { api } from './api'
import { EMAIL, appUrl } from './env'

type BackendMember = { id: number; email: string | null }

test('the board sets an own fee and the member confirms the reason', async ({ page }) => {
  await page.goto(appUrl('members'))
  const { data } = await api<{ data: BackendMember[] }>(
    page,
    'GET',
    `/members?search=${encodeURIComponent(EMAIL)}`,
  )
  const me = data.find((m) => m.email === EMAIL)!
  const until = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10)

  try {
    await page.goto(appUrl(`members/${me.id}`))
    await page.getByTestId('fee-edit').click()
    await page.getByText('Ermässigung', { exact: true }).click()
    await page.getByTestId('fee-reason').fill('E2E: in Ausbildung')
    await page.getByTestId('fee-until').fill(until)
    await page.getByTestId('fee-save').click()
    await expect(page.getByTestId('fee-own')).toHaveText('50 % weniger')

    // The member's own view: the reason and the confirmation.
    await page.goto(appUrl('account/settings/membership'))
    const card = page.getByTestId('my-fee')
    await expect(card.getByText('E2E: in Ausbildung')).toBeVisible()
    await card.getByTestId('my-fee-note').fill('Ausbildung läuft bis 2028')
    await card.getByTestId('my-fee-confirm').click()
    await expect(card.getByText(/bestätigt, dass der Grund noch zutrifft/)).toBeVisible()

    await page.goto(appUrl(`members/${me.id}`))
    await expect(page.getByTestId('fee-member-note')).toHaveText('Ausbildung läuft bis 2028')
  } finally {
    await api(page, 'DELETE', `/tiers/members/${me.id}/fee`).catch(() => undefined)
  }
})
