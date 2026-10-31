import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

test('a notification opens what it is about and can be deleted', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  // A poll reminder for a group the admin is in reaches the admin.
  const group = await api<{ id: number }>(page, 'POST', '/groups/', {
    name: unique('E2E Gruppe'),
    visibility: 'open',
  })
  const question = unique('E2E Erinnerung')
  let pollId: number | null = null
  try {
    await api(page, 'POST', `/groups/${group.id}/join`)
    const poll = await api<{ id: number }>(page, 'POST', '/polls/', {
      question,
      options: [{ label: 'Ja' }, { label: 'Nein' }],
      is_required: true,
      required_group_ids: [group.id],
    })
    pollId = poll.id
    await api(page, 'POST', `/polls/${poll.id}/remind`)

    await page.reload()
    await page.getByRole('button', { name: /^Benachrichtigungen/ }).click()
    const panel = page.getByRole('dialog', { name: 'Benachrichtigungen' })
    await panel.getByText(`Erinnerung: ${question}`).click()
    await expect(page).toHaveURL(new RegExp(`/app/operations/polls\\?poll=${poll.id}$`))
    await expect(page.getByText('Du siehst die Umfrage aus deiner Benachrichtigung.')).toBeVisible()

    // Opening it marked it read; now delete it.
    await page.getByRole('button', { name: /^Benachrichtigungen/ }).click()
    const row = panel.locator('.hb-notif', { hasText: question })
    await expect(row).not.toHaveAttribute('data-unread')
    await row.getByRole('button', { name: 'Löschen' }).click()
    await expect(row).toHaveCount(0)
    const left = await api<{ data: { title: string }[] }>(page, 'GET', '/notifications/')
    expect(left.data.some((n) => n.title.includes(question))).toBe(false)
  } finally {
    if (pollId) await api(page, 'DELETE', `/polls/${pollId}`)
    await api(page, 'DELETE', `/groups/${group.id}`)
  }
})
