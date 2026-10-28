import { test, expect } from '@playwright/test'

// Backend-shaped user (RawMember / snake_case, matching adaptMember in auth.ts)
const MOCK_USER = {
  id: 1,
  first_name: 'Test',
  last_name: 'User',
  name: 'Test User',
  email: 'test@example.com',
  public_email: 'test@hubra.club',
  tier: { name: 'Standard' },
  roles: [{ name: 'Member' }],
  status: 'active',
  tool_hours: 0,
  notes: null,
  avatar_color: '#fece2b',
  joined: '2024-01-01',
  last_seen: '2024-01-01T00:00:00',
}

// Mail settings responses — private_email_verified drives the verification UI
const UNVERIFIED_MAIL_SETTINGS = {
  forwarding_enabled: false,
  mailbox_enabled: false,
  private_email_verified: false,
}

const VERIFIED_MAIL_SETTINGS = {
  forwarding_enabled: false,
  mailbox_enabled: false,
  private_email_verified: true,
}

// Mock all backend API routes.
// Catch-all is registered FIRST (lowest priority in Playwright LIFO matching);
// specific routes come AFTER and therefore take precedence.
// Note: /account/mail-settings is NOT registered here — it is registered per-test
// AFTER seedAuth so it has higher priority than the /account/ catch from seedAuth.
async function mockApi(page: import('@playwright/test').Page) {
  const emptyList = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  const emptyObj = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

  // 1. Catch-all FIRST (overridden by specific routes below in LIFO order)
  await page.route('**/api/v1/**', emptyObj)

  // 2. Specific routes AFTER (matched before catch-all in LIFO order)
  await page.route('**/api/v1/auth/bootstrap-status', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ bootstrapped: true }),
    }),
  )
  await page.route('**/api/v1/events**', emptyList)
  await page.route('**/api/v1/polls**', emptyList)
  await page.route('**/api/v1/invoices**', emptyList)
  await page.route('**/api/v1/notifications**', emptyList)
  await page.route('**/api/v1/applications**', emptyList)
  await page.route('**/api/v1/groups**', emptyList)
  await page.route('**/api/v1/finance/**', emptyList)
  await page.route('**/api/v1/dashboard/summary', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stats: {
          activeMembers: 0,
          pendingApplications: 0,
          openInvoices: 0,
          upcomingEvents: 0,
        },
      }),
    }),
  )
  // /account/groups → empty array (getMyGroups in AccountSettingsScreen)
  await page.route('**/api/v1/account/groups', emptyList)
}

// Set auth tokens and mock /account/ (used by AppContext + AccountSettingsScreen
// via getAccount()).  Registered AFTER mockApi so this route has highest priority.
async function seedAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('hubra_phase', 'app')
  })
  // Exact trailing-slash path — does NOT match /account/mail-settings or /account/groups
  await page.route('**/api/v1/account/', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    }),
  )
}

test.describe('S03 UAT — Account Settings verification UI states', () => {
  // UAT-1: unverified user sees the verification banner and a disabled toggle
  test('unverified: shows Verify email button and disabled toggle', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)  // /account/ registered → high priority
    // /account/mail-settings registered LAST → wins over /account/ pattern in LIFO
    await page.route('**/api/v1/account/mail-settings', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(UNVERIFIED_MAIL_SETTINGS),
      }),
    )

    await page.goto('/account/settings')

    // Verification banner must be visible
    await expect(
      page.getByText('Verify your private email to enable forwarding'),
    ).toBeVisible()

    // "Send verification email" action button must be visible inside the banner
    await expect(
      page.getByRole('button', { name: /send verification email/i }),
    ).toBeVisible()

    // The forwarding toggle's underlying checkbox must be disabled
    await expect(page.locator('label.toggle input[type="checkbox"]')).toBeDisabled()
  })

  // UAT-2: verified user sees no verification banner and an enabled toggle
  test('verified: forwarding toggle is enabled', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    // /account/mail-settings registered LAST → highest priority
    await page.route('**/api/v1/account/mail-settings', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(VERIFIED_MAIL_SETTINGS),
      }),
    )

    await page.goto('/account/settings')

    // Verification banner must NOT be present
    await expect(
      page.getByText('Verify your private email to enable forwarding'),
    ).not.toBeVisible()

    // The forwarding toggle's underlying checkbox must be enabled (not disabled)
    await expect(page.locator('label.toggle input[type="checkbox"]')).not.toBeDisabled()
  })
})
