import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('the yearly expenses show where the sum comes from before saving', async ({ page }) => {
  const name = unique('Vereinslokal')
  const rule = await api<{ id: number }>(page, 'POST', '/finance/recurring', {
    description: name,
    type: 'expense',
    amount: 300,
    interval: 'monthly',
    start_date: new Date().toISOString().slice(0, 10),
    counts_for_fees: true,
  })

  await page.goto(appUrl('finance/fee-basis'))
  await page.getByRole('radio', { name: 'Wiederkehrende Ausgaben' }).check()
  // A preview: the rule is listed with its category's share of the sum.
  await expect(page.getByText(new RegExp(`${name} \\(300\\.00 monatlich\\)`))).toBeVisible()
  await page.getByLabel('Zusätzliche Kosten pro Jahr (CHF)').fill('123')
  await expect(page.getByRole('button', { name: 'Speichern' })).toBeEnabled()

  await page.getByRole('button', { name: 'Zurücksetzen' }).click()
  await expect(page.getByRole('button', { name: 'Speichern' })).toBeDisabled()

  await api(page, 'DELETE', `/finance/recurring/${rule.id}`)
})
