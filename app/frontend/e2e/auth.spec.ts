import { expect, test } from '@playwright/test'
import { SSO_URL, appUrl } from './env'

test.use({ storageState: { cookies: [], origins: [] } })

test('a signed-out visitor is sent to the sign-in and back to the page they asked for', async ({
  page,
}) => {
  await page.goto(appUrl('members'))
  await page.waitForURL(`${SSO_URL}/login**`)
  const redirect = new URL(page.url()).searchParams.get('redirect')
  expect(redirect).toBe(appUrl('members'))
})
