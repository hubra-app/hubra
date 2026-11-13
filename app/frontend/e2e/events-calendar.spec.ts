import { expect, test } from '@playwright/test'
import { appUrl } from './env'

test('Anlässe opens the club calendar with only the events', async ({ page }) => {
  await page.goto(appUrl('operations/events'))
  await page.getByTestId('events-calendar').click()
  await expect(page).toHaveURL(/\/app\/calendar\?only=event/)
  await expect(page.getByTestId('calendar-title')).toBeVisible()
})
