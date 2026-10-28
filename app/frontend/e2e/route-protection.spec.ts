import { test, expect, type Page, type Route } from '@playwright/test'

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

const ADMIN_USER = {
  ...MOCK_USER,
  roles: [{ name: 'Admin' }],
}

const EMPTY_OBJ = (r: Route) =>
  r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

async function mockAuth(
  page: Page,
  user: typeof MOCK_USER,
  permissions: { is_admin: boolean; permissions: string[] },
) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('hubra_phase', 'app')
  })

  await page.route('**/api/v1/bootstrap-status', (r) =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ bootstrapped: true }),
    }),
  )

  await page.route('**/api/v1/account/', (r) =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    }),
  )

  await page.route('**/api/v1/account/permissions', (r) =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(permissions),
    }),
  )

  await page.route('**/api/v1/features', (r) =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { key: 'mail', enabled: true },
        { key: 'events', enabled: true },
        { key: 'polls', enabled: true },
        { key: 'posts', enabled: true },
      ]),
    }),
  )

  await page.route('**/api/v1/dashboard/summary', (r) =>
    r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stats: { activeMembers: 0, pendingApplications: 0, openInvoices: 0, upcomingEvents: 0 },
      }),
    }),
  )

  // Catch-all for remaining API calls
  await page.route('**/api/v1/**', EMPTY_OBJ)
}

test.describe('Route protection — frontend authorization guards', () => {
  test.describe('Unauthenticated user', () => {
    test('redirected to /login from protected routes', async ({ page }) => {
      await page.addInitScript(() => {
        sessionStorage.setItem('hubra_phase', 'login')
      })
      await page.route('**/api/v1/bootstrap-status', (r) =>
        r.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ bootstrapped: true }),
        }),
      )
      await page.route('**/api/v1/**', EMPTY_OBJ)

      await page.goto('/app/dashboard')
      await expect(page).toHaveURL(/\/login/)
    })
  })

  test.describe('Member with no permissions', () => {
    test.beforeEach(async ({ page }) => {
      await mockAuth(page, MOCK_USER, { is_admin: false, permissions: [] })
    })

    test('sees Access Denied on /app/settings', async ({ page }) => {
      await page.goto('/app/settings')
      await expect(page.getByText(/access denied/i)).toBeVisible()
    })

    test('sees Access Denied on /app/system', async ({ page }) => {
      await page.goto('/app/system')
      await expect(page.getByText(/access denied/i)).toBeVisible()
    })

    test('sees Access Denied on /app/audit-log', async ({ page }) => {
      await page.goto('/app/audit-log')
      await expect(page.getByText(/access denied/i)).toBeVisible()
    })

    test('sees Access Denied on /app/operations/bindings', async ({ page }) => {
      await page.goto('/app/operations/bindings')
      await expect(page.getByText(/access denied/i)).toBeVisible()
    })

    test('can access dashboard (no permission required)', async ({ page }) => {
      await page.goto('/app/dashboard')
      await expect(page).toHaveURL(/\/app\/dashboard/)
    })

    test('can access account settings (self-service)', async ({ page }) => {
      await page.goto('/app/account/settings')
      await expect(page).toHaveURL(/\/app\/account\/settings/)
    })
  })

  test.describe('Member with settings read permission', () => {
    test.beforeEach(async ({ page }) => {
      await mockAuth(page, MOCK_USER, {
        is_admin: false,
        permissions: ['settings.settings.read'],
      })
    })

    test('can access /app/settings', async ({ page }) => {
      await page.goto('/app/settings')
      await expect(page).toHaveURL(/\/app\/settings/)
    })

    test('still denied on /app/system', async ({ page }) => {
      await page.goto('/app/system')
      await expect(page.getByText(/access denied/i)).toBeVisible()
    })
  })

  test.describe('Member with roles.create permission', () => {
    test.beforeEach(async ({ page }) => {
      await mockAuth(page, MOCK_USER, {
        is_admin: false,
        permissions: ['roles.roles.create'],
      })
    })

    test('can access /app/system', async ({ page }) => {
      await page.goto('/app/system')
      await expect(page).toHaveURL(/\/app\/system/)
    })
  })

  test.describe('Member with audit.read permission', () => {
    test.beforeEach(async ({ page }) => {
      await mockAuth(page, MOCK_USER, {
        is_admin: false,
        permissions: ['audit.audit.read'],
      })
    })

    test('can access /app/audit-log', async ({ page }) => {
      await page.goto('/app/audit-log')
      await expect(page).toHaveURL(/\/app\/audit-log/)
    })
  })

  test.describe('Admin user (is_admin)', () => {
    test.beforeEach(async ({ page }) => {
      await mockAuth(page, ADMIN_USER, { is_admin: true, permissions: ['*'] })
    })

    test('can access /app/settings', async ({ page }) => {
      await page.goto('/app/settings')
      await expect(page).toHaveURL(/\/app\/settings/)
    })

    test('can access /app/system', async ({ page }) => {
      await page.goto('/app/system')
      await expect(page).toHaveURL(/\/app\/system/)
    })

    test('can access /app/audit-log', async ({ page }) => {
      await page.goto('/app/audit-log')
      await expect(page).toHaveURL(/\/app\/audit-log/)
    })
  })

  test.describe('Feature-gated routes', () => {
    test('redirects to dashboard when mail feature is disabled', async ({
      page,
    }) => {
      await mockAuth(page, MOCK_USER, { is_admin: false, permissions: [] })
      // Override features to disable mail
      await page.route('**/api/v1/features', (r) =>
        r.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { key: 'mail', enabled: false },
            { key: 'events', enabled: true },
            { key: 'polls', enabled: true },
            { key: 'posts', enabled: true },
          ]),
        }),
      )

      await page.goto('/app/mail')
      await expect(page).toHaveURL(/\/app\/dashboard/)
    })
  })

  test.describe('AccessDenied screen content', () => {
    test('shows "Go to dashboard" button', async ({ page }) => {
      await mockAuth(page, MOCK_USER, { is_admin: false, permissions: [] })
      await page.goto('/app/settings')
      await expect(page.getByRole('button', { name: /go to dashboard/i })).toBeVisible()
    })

    test('navigates to dashboard when button clicked', async ({ page }) => {
      await mockAuth(page, MOCK_USER, { is_admin: false, permissions: [] })
      await page.goto('/app/settings')
      await page.getByRole('button', { name: /go to dashboard/i }).click()
      await expect(page).toHaveURL(/\/app\/dashboard/)
    })
  })
})
