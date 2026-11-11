import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a must-read post is confirmed on its page', async ({ page }) => {
  await page.goto(appUrl('operations/posts'))
  const title = unique('E2E Platzregeln')
  const post = await api<{ id: number }>(page, 'POST', '/posts/', {
    title,
    body: 'Bitte nach dem Training die Maschinen reinigen.',
    must_read: true,
  })
  try {
    await page.goto(appUrl(`operations/posts/${post.id}`))
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    await page.getByTestId('confirm-read').click()
    await expect(page.getByTestId('must-read-row')).toContainText('Gelesen bestätigt')
    await page.getByTestId('detail-back').click()
    await expect(page).toHaveURL(/operations\/posts$/)
  } finally {
    await api(page, 'DELETE', `/posts/${post.id}`)
  }
})
