import { test, expect } from '@playwright/test'

const MOCK_USER = {
  id: 1,
  first_name: 'Test',
  last_name: 'User',
  name: 'Test User',
  email: 'test@example.com',
  public_email: 'test@vollbuild.ch',
  tier: { name: 'Standard' },
  roles: [{ name: 'Member' }],
  status: 'active',
  tool_hours: 0,
  notes: null,
  avatar_color: '#fece2b',
  avatar: null,
  profile_note: null,
  joined: '2024-01-01',
  last_seen: '2024-01-01',
  private_email_verified: true,
  must_change_password: false,
}

// Set auth tokens before the app initialises
async function seedAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('hubra_phase', 'app')
  })
  await page.route('**/api/v1/account/', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )
}

// Mock all backend API routes so the spec works without a running backend
async function mockApi(page: import('@playwright/test').Page) {
  const emptyList = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  const emptyObj = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

  // Auth: return mock user for /me
  await page.route('**/api/v1/auth/me', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )

  // Nav counts and lists
  await page.route('**/api/v1/dashboard/summary', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ stats: { activeMembers: 0, pendingApplications: 0, openInvoices: 0, upcomingEvents: 0 } }) })
  )
  await page.route('**/api/v1/events**', emptyList)
  await page.route('**/api/v1/polls**', emptyList)
  await page.route('**/api/v1/invoices**', emptyList)
  await page.route('**/api/v1/notifications**', emptyList)
  await page.route('**/api/v1/members**', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ members: [], total: 0 }) })
  )
  await page.route('**/api/v1/applications**', emptyList)
  await page.route('**/api/v1/groups**', emptyList)
  await page.route('**/api/v1/finance/**', emptyList)

  // Catch-all for any remaining API calls
  await page.route('**/api/v1/**', emptyObj)
}

test.describe('S09 smoke — Account Settings tabs and Poll/Event screens', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page)
  })

  test('Account Settings screen renders with all four tabs', async ({ page }) => {
    await page.goto('/account/settings')
    await expect(page.getByRole('heading', { name: /account settings/i })).toBeVisible()

    // All four tab buttons must be present in the DOM
    await expect(page.getByRole('button', { name: /^profile$/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /membership/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /payment settings/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /security/i })).toBeVisible()
  })

  test('Profile tab shows profile and notification sections', async ({ page }) => {
    await page.goto('/account/settings')
    await page.getByRole('button', { name: /^profile$/i }).click()
    await expect(page.getByText('Notification preferences')).toBeVisible()
  })

  test('Membership tab shows membership details', async ({ page }) => {
    await page.goto('/account/settings')
    await page.getByRole('button', { name: /membership/i }).click()
    await expect(page.getByText('Membership details')).toBeVisible()
  })

  test('Payment settings tab shows payment method options', async ({ page }) => {
    await page.goto('/account/settings')
    await page.getByRole('button', { name: /payment settings/i }).click()
    await expect(page.getByText('Preferred payment method')).toBeVisible()
  })

  test('Security tab shows change password section', async ({ page }) => {
    await page.goto('/account/settings')
    await page.getByRole('button', { name: /security/i }).click()
    await expect(page.getByText('Change password')).toBeVisible()
  })

  test('Events screen is reachable as a standalone route', async ({ page }) => {
    await page.goto('/events')
    await expect(page.getByRole('heading', { name: /^events$/i })).toBeVisible()
  })

  test('Polls screen is reachable as a standalone route', async ({ page }) => {
    await page.goto('/events/polls')
    await expect(page.getByRole('heading', { name: /^polls$/i })).toBeVisible()
  })
})
