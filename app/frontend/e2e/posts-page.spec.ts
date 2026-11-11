import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('Beiträge: the must-read banner, the filter and a post page', async ({ page }) => {
  await page.goto(appUrl('operations/posts'))
  const title = unique('E2E Platzregeln')
  const post = await api<{ id: number }>(page, 'POST', '/posts/', {
    title,
    body: 'Bitte nach dem Training die Maschinen reinigen.',
    must_read: true,
  })
  try {
    await page.reload()
    await expect(page.getByTestId('must-read-banner')).toBeVisible()
    await page.getByTestId('must-read-banner').getByRole('button', { name: 'Anzeigen' }).click()
    const card = page.getByTestId('post-card').filter({ hasText: title })
    await expect(card).toBeVisible()

    await card.getByTestId('post-title').click()
    await expect(page).toHaveURL(new RegExp(`operations/posts/${post.id}$`))
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    await page.getByTestId('confirm-read').click()
    await expect(page.getByTestId('must-read-row')).toContainText('Gelesen bestätigt')

    await page.getByTestId('detail-back').click()
    await page.getByPlaceholder('Beiträge durchsuchen …').fill(title)
    await expect(page.getByTestId('post-card')).toHaveCount(1)
  } finally {
    await api(page, 'DELETE', `/posts/${post.id}`)
  }
})
