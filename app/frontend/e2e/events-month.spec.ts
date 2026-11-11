import { expect, test } from '@playwright/test'
import { appUrl } from './env'

test('Anlässe switches between the list and the month', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  await page.getByTestId('events-view').locator('label', { hasText: 'Monat' }).click()
  await expect(page.getByTestId('events-month')).toBeVisible()
  // Back to the list for the other tests on this device.
  await page.getByTestId('events-view').locator('label', { hasText: 'Liste' }).click()
  await expect(page.getByTestId('events-month')).toBeHidden()
})
