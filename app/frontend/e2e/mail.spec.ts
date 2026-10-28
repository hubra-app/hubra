import { test, expect } from '@playwright/test'

// Backend-shaped user (snake_case, matching RawMember in auth.ts)
const MOCK_USER = {
  id: 1,
  first_name: 'Test',
  last_name: 'Admin',
  name: 'Test Admin',
  email: 'admin@vollbuild.ch',
  public_email: 'admin@vollbuild.ch',
  tier: { name: 'Standard' },
  roles: [{ name: 'Admin' }],
  status: 'active',
  tool_hours: 0,
  notes: null,
  avatar_color: '#fece2b',
  joined: '2024-01-01',
  last_seen: '2024-01-01T00:00:00',
}

// Backend-shaped mail member (snake_case consumed by adaptMailMember)
const MOCK_MEMBER_BACKEND = {
  id: '1',
  name: 'Anna Huber',
  public_email: 'anna@vollbuild.ch',
  mailbox_enabled: false,
  forwarding_enabled: false,
  retention_days: 90,
  wildduck_id: null,
}

// Backend-shaped group (snake_case consumed by adapt in groups.ts)
const MOCK_GROUP_BACKEND = {
  id: 1,
  name: 'Werkstatt',
  lead_id: null,
  lead_name: null,
  description: null,
  color: null,
  icon_name: null,
  member_count: 3,
  sessions: null,
  tools: 0,
  is_default: false,
  wildduck_alias_id: null,
  mail_enabled: false,
  forwarding_enabled: false,
  allow_send_as: false,
}

// Backend-shaped alias (camelCase — matches BackendAlias interface in mail.ts)
const MOCK_ALIAS = {
  id: 'wd-1',
  address: 'werkstatt@vollbuild.ch',
  type: 'Distribution',
  deliversTo: ['a@b.com'],
  enabled: true,
  groupId: 1,
  groupName: 'Werkstatt',
}

// Mock all backend API routes.
// Catch-all is registered FIRST (lowest priority in Playwright LIFO matching);
// specific routes come AFTER and therefore take precedence.
async function mockApi(page: import('@playwright/test').Page) {
  const emptyList = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  const emptyObj = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

  // 1. Catch-all FIRST (overridden by specific routes below)
  await page.route('**/api/v1/**', emptyObj)

  // 2. Specific routes AFTER (matched before catch-all in LIFO order)
  await page.route('**/api/v1/auth/bootstrap-status', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ bootstrapped: true }) })
  )
  await page.route('**/api/v1/events**', emptyList)
  await page.route('**/api/v1/polls**', emptyList)
  await page.route('**/api/v1/invoices**', emptyList)
  await page.route('**/api/v1/notifications**', emptyList)
  await page.route('**/api/v1/applications**', emptyList)
  // Groups: used by AppContext (nav count) and GroupMailScreen
  await page.route('**/api/v1/groups', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_GROUP_BACKEND]) })
  )
  // Mail members list
  await page.route('**/api/v1/mail/members', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [MOCK_MEMBER_BACKEND] }) })
  )
  // Aliases list
  await page.route('**/api/v1/mail/aliases', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [MOCK_ALIAS] }) })
  )
  // CRITICAL: proper stats object prevents ErrorBoundary crash from s.stats.activeMembers TypeError
  await page.route('**/api/v1/dashboard/summary', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stats: { activeMembers: 0, pendingApplications: 0, openInvoices: 0, upcomingEvents: 0 },
      }),
    })
  )
}

// Set auth tokens before the app initialises so it starts in the 'app' phase.
// Registered AFTER mockApi so /account/ route has highest priority.
async function seedAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('vollbuild_phase', 'app')
  })
  // Exact path /account/ (not **/account/**) — trailing ** doesn't match empty segment
  await page.route('**/api/v1/account/', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )
}

test.describe('Mail admin UAT — member mail, group mail, alias delete block', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)   // FIRST: registers catch-all + base specific routes
    await seedAuth(page)  // SECOND: /account/ gets higher priority than mockApi routes
  })

  // UAT-1: Member mail tab shows member row and toggling mailbox_enabled calls PATCH
  test('member mail tab shows member row and toggling mailbox_enabled calls PATCH', async ({ page }) => {
    // Capture the PATCH request BEFORE navigating so the promise is ready
    const patchRequest = page.waitForRequest(
      req => req.url().includes('/api/v1/mail/members/1') && req.method() === 'PATCH',
    )

    // Register PATCH handler (registered after beforeEach → highest priority in LIFO)
    await page.route('**/api/v1/mail/members/1', async route => {
      if (route.request().method() === 'PATCH') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...MOCK_MEMBER_BACKEND, mailbox_enabled: true }),
        })
      } else {
        await route.continue()
      }
    })

    await page.goto('/mail/members')
    await expect(page.locator('[data-testid="member-mail-table"]')).toBeVisible()

    // Locate Anna Huber's row and click the first toggle label (Mailbox column)
    const row = page.locator('[data-testid="member-mail-table"] tbody tr', { hasText: 'Anna Huber' })
    await expect(row).toBeVisible()
    await row.locator('label.toggle').first().click()

    // Verify PATCH was called with mailbox_enabled: true
    const req = await patchRequest
    const body = req.postDataJSON() as Record<string, unknown>
    expect(body).toMatchObject({ mailbox_enabled: true })
  })

  // UAT-2: Provision button calls POST /mail/members/1/provision
  test('provision button calls POST provision endpoint', async ({ page }) => {
    const postRequest = page.waitForRequest(
      req => req.url().includes('/api/v1/mail/members/1/provision') && req.method() === 'POST',
    )

    await page.route('**/api/v1/mail/members/1/provision', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_MEMBER_BACKEND, wildduck_id: 'wd-provisioned-123' }),
      })
    })

    await page.goto('/mail/members')
    await expect(page.locator('[data-testid="member-mail-table"]')).toBeVisible()

    // Provision button is disabled when wildduck_id is set; Anna has wildduck_id: null so it is enabled
    await page.getByTestId('provision-btn-1').click()

    await postRequest // resolves when POST fires — sufficient assertion
  })

  // UAT-3: Group mail tab shows group card and toggling mail_enabled calls PATCH
  test('group mail tab shows group card and toggling mail_enabled calls PATCH', async ({ page }) => {
    const patchRequest = page.waitForRequest(
      req => req.url().includes('/api/v1/groups/1/mail') && req.method() === 'PATCH',
    )

    await page.route('**/api/v1/groups/1/mail', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_GROUP_BACKEND, mail_enabled: true }),
      })
    })

    await page.goto('/mail/groups')
    await expect(page.locator('[data-testid="group-mail-grid"]')).toBeVisible()

    // Locate the Werkstatt card and click the first toggle label (Mail enabled)
    const card = page.locator('[data-testid="group-mail-grid"] .card', { hasText: 'Werkstatt' })
    await expect(card).toBeVisible()
    await card.locator('label.toggle').first().click()

    // Verify PATCH was called with mail_enabled: true
    const req = await patchRequest
    const body = req.postDataJSON() as Record<string, unknown>
    expect(body).toMatchObject({ mail_enabled: true })
  })

  // UAT-4: Attempting to delete a group-linked alias shows 'Delete failed' error toast
  test('aliases tab delete blocked alias shows error toast', async ({ page }) => {
    // Return 409 for DELETE on the group-linked alias
    await page.route('**/api/v1/mail/aliases/wd-1', async route => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'CONFLICT',
            message: 'Alias is tied to group Werkstatt — disable mail_enabled on the group first',
          }),
        })
      } else {
        await route.continue()
      }
    })

    await page.goto('/mail/aliases')

    // Click delete (trash icon) in the werkstatt@vollbuild.ch row
    const row = page.locator('table tbody tr', { hasText: 'werkstatt@vollbuild.ch' })
    await expect(row).toBeVisible()
    await row.locator('button').click()

    // Confirm deletion in the modal (the danger "Delete" button)
    await page.locator('.modal-box').getByRole('button', { name: /delete/i }).click()

    // Error toast with 'Delete failed' title must appear
    await expect(page.locator('.toast.error', { hasText: 'Delete failed' })).toBeVisible()
  })
})
