import { test, expect } from '@playwright/test'

const MOCK_USER = {
  id: 1,
  first_name: 'Test',
  last_name: 'User',
  name: 'Test User',
  email: 'test@example.com',
  public_email: 'test@vollbuild.ch',
  tier: { name: 'Standard' },
  roles: [{ name: 'Admin' }],
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

async function seedAuth(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('vollbuild_phase', 'app')
  })
  // Catch-all FIRST (lowest priority — must be registered before specific routes)
  await page.route('**/api/v1/**', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  )
  // Specific routes AFTER (higher priority — override catch-all)
  await page.route('**/api/v1/auth/bootstrap-status', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ bootstrapped: true }) })
  )
  await page.route('**/api/v1/health', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
  )
  await page.route('**/api/v1/account/', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )
  await page.route('**/api/v1/account/permissions', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ is_admin: true, permissions: ['*'] }) })
  )
  await page.route('**/api/v1/dashboard/summary', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      stats: { activeMembers: 0, memberDelta: 0, netMonth: 0, openInvoices: 0, openInvoicesAmount: 0, upcomingEvents: 0 },
      growth: [],
      upcomingEvents: [],
      posts: [],
    }) })
  )
}

const MOCK_PERMISSIONS = [
  { method: 'GET', path: '/api/v1/members', key: 'member:list', display_name: 'List Members', resource: 'member', action: 'list', blueprint: 'members' },
  { method: 'POST', path: '/api/v1/members', key: 'member:create', display_name: 'Create Member', resource: 'member', action: 'create', blueprint: 'members' },
  { method: 'DELETE', path: '/api/v1/members/{id}', key: 'member:delete', display_name: 'Delete Member', resource: 'member', action: 'delete', blueprint: 'members' },
]

const MOCK_ROLES = [
  { id: 'role-1', name: 'Admin', slug: 'admin', isAdmin: true, isDefault: false, permissions: ['member:list', 'member:create', 'member:delete'] },
  { id: 'role-2', name: 'Member', slug: 'member', isAdmin: false, isDefault: true, permissions: ['member:list'] },
]

const MOCK_PERMISSION_TREE = [
  { bp: 'members', label: 'Members', permissions: [
    { key: 'member:list', name: 'List Members', description: '' },
    { key: 'member:create', name: 'Create Member', description: '' },
    { key: 'member:delete', name: 'Delete Member', description: '' },
  ]},
]

async function mockApi(page: import('@playwright/test').Page) {
  // System-specific routes (registered after seedAuth's catch-all, so higher priority)
  await page.route('**/api/v1/auth/me', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )
  await page.route('**/api/v1/system/permissions', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PERMISSIONS) })
  )
  await page.route('**/api/v1/roles', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ROLES) })
  )
  await page.route('**/api/v1/system/permission-tree', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PERMISSION_TREE) })
  )
}

test.describe('Responsive tables stack on mobile, matrix tables preserved', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page)
  })

  test('inline Table on System permissions tab stacks at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('http://localhost:80/app/system')

    await page.waitForSelector('table')

    const thead = page.locator('table thead')
    await expect(thead).not.toBeVisible()

    const firstCell = page.locator('table tbody tr:first-child td').first()
    await expect(firstCell).toBeVisible()

    // Card layout: rows have border-radius and flex direction
    const trStyle = await page.locator('table tbody tr').first().evaluate(
      (el) => ({
        display: getComputedStyle(el).display,
        borderRadius: getComputedStyle(el).borderRadius,
      })
    )
    expect(trStyle.display).toBe('flex')
    expect(trStyle.borderRadius).not.toBe('0px')

    // Fields are stacked vertically (flex-direction: column)
    const tdFlexDir = await firstCell.evaluate(
      (el) => getComputedStyle(el).flexDirection
    )
    expect(tdFlexDir).toBe('column')
  })

  test('RolesTab matrix table preserves thead at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('http://localhost:80/app/system/roles')

    await page.waitForSelector('table')

    const thead = page.locator('table thead')
    await expect(thead.first()).toBeVisible()
  })

  test('inline Table on System permissions tab shows data-label on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('http://localhost:80/app/system')

    await page.waitForSelector('table')

    const td = page.locator('table tbody tr:first-child td').first()
    const label = await td.getAttribute('data-label')
    expect(label).toBeTruthy()
  })
})
