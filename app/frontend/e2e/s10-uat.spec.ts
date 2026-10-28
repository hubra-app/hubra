import { test, expect } from '@playwright/test'

// Raw member shape matching the backend wire format (before adaptMember transforms it)
const RAW_MOCK_MEMBER = {
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
  last_seen: '2024-01-01',
}

// Mock all backend API routes so the spec runs without a live backend.
// Playwright uses LIFO route matching: the LAST registered handler wins.
// So: register the catch-all FIRST (lowest priority), specific routes AFTER (higher priority).
// Callers must invoke mockApi() BEFORE registering test-specific overrides so those
// test-specific mocks (registered last) take precedence over the catch-all.
async function mockApi(page: import('@playwright/test').Page) {
  const emptyList = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  const emptyObj = (r: import('@playwright/test').Route) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

  // Catch-all FIRST (lowest priority — overridden by anything registered after)
  await page.route('**/api/v1/**', emptyObj)
  // Specific mocks AFTER (higher priority than catch-all)
  await page.route('**/api/v1/finance/**', emptyList)
  await page.route('**/api/v1/groups**', emptyList)
  await page.route('**/api/v1/applications**', emptyList)
  await page.route('**/api/v1/members**', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ members: [], total: 0 }),
    })
  )
  await page.route('**/api/v1/notifications**', emptyList)
  await page.route('**/api/v1/polls**', emptyList)
  await page.route('**/api/v1/events**', emptyList)
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

// Seeds localStorage tokens + sessionStorage phase so the React app boots into
// the authenticated 'app' phase without performing a real login flow.
// Call AFTER test-specific route mocks but BEFORE mockApi().
async function seedAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('hubra_phase', 'app')
  })
  // Handles both the session-restore GET and the profile-save PATCH on /account/
  await page.route('**/api/v1/account/', r =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(RAW_MOCK_MEMBER),
    })
  )
}

test.describe('S10 UAT — Login flow and password reset', () => {
  test('Login flow: valid credentials navigates to dashboard', async ({ page }) => {
    // mockApi first (catch-all lowest priority), then specific mock last (wins with LIFO)
    await mockApi(page)
    await page.route('**/api/v1/auth/login', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          accessToken: 'tok',
          refreshToken: 'ref',
          member: RAW_MOCK_MEMBER,
        }),
      })
    )

    await page.goto('/login')
    await page.locator('input[type="email"]').fill('test@example.com')
    await page.locator('input[type="password"]').fill('password123')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await page.waitForURL('**/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('Login flow: invalid credentials shows error message', async ({ page }) => {
    // mockApi first (catch-all lowest priority), then 401 mock last (wins with LIFO)
    await mockApi(page)
    await page.route('**/api/v1/auth/login', r =>
      r.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Invalid credentials' }),
      })
    )

    await page.goto('/login')
    await page.locator('input[type="email"]').fill('wrong@example.com')
    await page.locator('input[type="password"]').fill('wrongpassword')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page.getByText('Invalid credentials').first()).toBeVisible()
  })

  test('Forgot password: submitting email shows reset link confirmation', async ({ page }) => {
    // mockApi first, then forgot-password mock last (wins with LIFO)
    await mockApi(page)
    await page.route('**/api/v1/auth/forgot-password', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'ok' }),
      })
    )

    await page.goto('/forgot-password')
    await page.locator('input[type="email"]').fill('user@example.com')
    await page.getByRole('button', { name: 'Send reset link' }).click()

    // After success, ForgotPassword renders the confirmation block:
    // "you'll receive a reset link within a few minutes."
    await expect(page.getByText(/reset link/i)).toBeVisible()
  })
})

test.describe('S10 UAT — Dashboard counters', () => {
  test('Stat tiles render active members and open invoices without placeholders', async ({ page }) => {
    // mockApi first (lowest priority), seedAuth second, then 42-members override last (wins with LIFO)
    await mockApi(page)
    await seedAuth(page)
    await page.route('**/api/v1/dashboard/summary', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          stats: {
            activeMembers: 42,
            memberDelta: 3,
            netMonth: 1500,
            openInvoices: 2,
            openInvoicesAmount: 240,
            upcomingEvents: 5,
          },
          growth: [],
          upcomingEvents: [],
          posts: [],
        }),
      })
    )
    await page.goto('/dashboard')

    // Stat tile values must show real numbers once the API resolves
    await expect(
      page.locator('.stat-tile').filter({ hasText: 'Active members' }).locator('.num')
    ).toHaveText('42')
    await expect(
      page.locator('.stat-tile').filter({ hasText: 'Open invoices' }).locator('.num')
    ).toHaveText('2')
    // No placeholder em-dash, 'undefined', or 'NaN' in any stat tile value
    await expect(page.locator('.stat-tile .num').filter({ hasText: '—' })).toHaveCount(0)
    await expect(page.locator('.stat-tile .num').filter({ hasText: 'undefined' })).toHaveCount(0)
    await expect(page.locator('.stat-tile .num').filter({ hasText: 'NaN' })).toHaveCount(0)
  })
})

test.describe('S10 UAT — Member self-service: profile edit', () => {
  test('Member edits display name and sees success toast', async ({ page }) => {
    // mockApi first, seedAuth last so account mock wins over catch-all (LIFO)
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/account/settings')

    // Profile tab is default; Display name is the first non-readonly input in the form
    const displayNameInput = page.locator('input.input:not([readonly])').first()
    await displayNameInput.fill('Updated')
    await page.getByRole('button', { name: /save profile/i }).click()

    await expect(page.getByText('Profile saved')).toBeVisible()
  })
})

test.describe('S10 UAT — Invoice list', () => {
  test('Member views invoice list with id, member name, and Open status', async ({ page }) => {
    // mockApi first, seedAuth second, invoice mock last (wins with LIFO over finance/** catch)
    await mockApi(page)
    await seedAuth(page)
    await page.route('**/api/v1/finance/invoices**', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            {
              id: 1001,
              member_id: 1,
              member_name: 'Test User',
              issued: '2026-01-01',
              due: '2026-02-01',
              amount: 120.0,
              status: 'Open',
            },
          ],
        }),
      })
    )
    await page.goto('/finance/invoices')

    // Invoice id rendered as String(1001) = "1001" in the table
    await expect(page.getByText('1001').first()).toBeVisible()
    await expect(page.locator('table.tbl td').filter({ hasText: 'Test User' }).first()).toBeVisible()
    await expect(page.locator('.pill').filter({ hasText: 'Open' }).first()).toBeVisible()
  })
})
