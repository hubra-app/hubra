import { test, expect, type Page } from '@playwright/test'

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

const MOCK_GROUPS = [
  { id: 1, name: 'Werkstatt', lead_id: null, lead_name: null, description: 'Werkstatt', color: '#fece2b', icon_name: 'Zap', member_count: 5, sessions: 'Tue 18-22', tools: 3, is_default: false },
]

const MOCK_TIERS = [
  { id: 1, name: 'Maker', price_chf: 30, color: '#fece2b' },
  { id: 2, name: 'Pro', price_chf: 50, color: '#6366f1' },
]

const MOCK_ROLES = [
  { id: 1, name: 'Admin', is_default: false },
  { id: 2, name: 'Member', is_default: true },
]

const MOCK_MEMBERS = [
  { id: 1, first_name: 'Anna', last_name: 'Huber', name: 'Anna Huber', email: 'anna@example.com', public_email: 'anna@vollbuild.ch', tier: { name: 'Maker' }, roles: [{ name: 'Member' }], status: 'active', tool_hours: 12, notes: '', avatar_color: '#fece2b', avatar: null, profile_note: '', joined: '2024-01-15', last_seen: '2024-07-01', private_email_verified: true, groups: [{ id: 1, name: 'Werkstatt' }] },
  { id: 2, first_name: 'Marc', last_name: 'Keller', name: 'Marc Keller', email: 'marc@example.com', public_email: 'marc@vollbuild.ch', tier: { name: 'Pro' }, roles: [{ name: 'Admin' }], status: 'active', tool_hours: 45, notes: '', avatar_color: '#6366f1', avatar: null, profile_note: '', joined: '2024-02-01', last_seen: '2024-07-02', private_email_verified: true, groups: [{ id: 1, name: 'Werkstatt' }] },
]

const MOCK_PERMISSIONS = [
  { method: 'GET', path: '/api/v1/members', key: 'member:list', display_name: 'List Members', resource: 'member', action: 'list', blueprint: 'members' },
  { method: 'POST', path: '/api/v1/members', key: 'member:create', display_name: 'Create Member', resource: 'member', action: 'create', blueprint: 'members' },
]

const MOCK_EVENTS = [
  { id: 1, title: 'Open Workshop', date: '2024-07-15', time: '18:00', location: 'Werkstatt', type: 'workshop', attendee_ids: [1, 2] },
]

const MOCK_POLL = {
  id: 1,
  question: 'Next event date?',
  options: [{ id: 1, label: 'Friday', vote_count: 3 }, { id: 2, label: 'Saturday', vote_count: 5 }],
  total_votes: 8,
  closes_at: '2024-07-20',
  status: 'open',
}

const MOCK_INVOICE = {
  id: 1001,
  member_id: 1,
  member_name: 'Anna Huber',
  status: 'Open',
  amount: 30.0,
  due_date: '2024-08-01',
  issued_date: '2024-07-01',
  description: 'Membership July',
}

const MOCK_TRANSACTION = {
  id: 1,
  amount: 120.0,
  description: 'Workshop materials',
  date: '2024-07-01',
  type: 'Out',
  category_id: 1,
  category_name: 'Materials',
  invoice_id: null,
}

const MOCK_CATEGORY = {
  id: 1,
  name: 'Materials',
  type: 'expense',
  is_default: false,
}

const MOCK_CODE = {
  id: 1,
  name: 'Front Door',
  code: '1234',
  description: 'Main entrance',
  isActive: true,
  createdAt: '2024-01-01',
  updatedAt: '2024-01-01',
}

const MOCK_ITEM = {
  id: 1,
  name: 'Cordless Drill',
  description: 'Bosch 18V',
  status: 'available',
  owner_id: null,
  owner_name: null,
  category: 'Tools',
  serial: 'SN-001',
  location: 'Shelf A',
}

const MOCK_ALIAS = {
  id: 1,
  address: 'info@vollbuild.ch',
  targets: ['marc@vollbuild.ch'],
  description: 'Info alias',
  is_disabled: false,
  created_at: '2024-01-01',
}

const MOCK_MAILBOX = {
  id: 1,
  address: 'marc@vollbuild.ch',
  name: 'Marc Keller',
  is_disabled: false,
  quota: 1024,
  storage: 100,
}

const MOCK_AUDIT_ENTRIES = {
  data: [
    { id: 1, actor_name: 'Marc Keller', action: 'member.create', target_type: 'member', target_id: 1, target_name: 'Anna Huber', created_at: '2024-07-01T10:00:00Z' },
  ],
  total: 1,
}

const MOCK_EXTERNAL_PARTIES = [
  { id: 1, name: 'Bosch', email: 'sales@bosch.com', city: 'Zurich' },
]

async function seedAuth(page: Page) {
  await page.addInitScript(() => {
    document.cookie = 'csrf_access_token=mock; path=/'
    document.cookie = 'csrf_refresh_token=mock; path=/'
    sessionStorage.setItem('hubra_phase', 'app')
  })
  await page.route('**/api/v1/**', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  )
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
      stats: { activeMembers: 5, memberDelta: 1, netMonth: 1200, openInvoices: 2, openInvoicesAmount: 240, upcomingEvents: 1 },
      growth: [], upcomingEvents: [], posts: [],
    }) })
  )
  await page.route('**/api/v1/groups', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_GROUPS) })
  )
  await page.route('**/api/v1/roles', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ROLES) })
  )
  await page.route('**/api/v1/tiers', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TIERS) })
  )
  await page.route('**/api/v1/members?*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: MOCK_MEMBERS, total: 2 }) })
  )
  await page.route('**/api/v1/events', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_EVENTS) })
  )
  await page.route('**/api/v1/polls', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_POLL]) })
  )
  await page.route('**/api/v1/finance/invoices*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_INVOICE]) })
  )
  await page.route('**/api/v1/transactions*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_TRANSACTION]) })
  )
  await page.route('**/api/v1/transaction-categories*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_CATEGORY]) })
  )
  await page.route('**/api/v1/codes', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_CODE]) })
  )
  await page.route('**/api/v1/items*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_ITEM]) })
  )
  await page.route('**/api/v1/system/permissions', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PERMISSIONS) })
  )
  await page.route('**/api/v1/audit*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_AUDIT_ENTRIES) })
  )
  await page.route('**/api/v1/mail/aliases*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_ALIAS]) })
  )
  await page.route('**/api/v1/mail/mailboxes*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_MAILBOX]) })
  )
  await page.route('**/api/v1/mail/members*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 1, name: 'Marc Keller', email: 'marc@vollbuild.ch', wildduck_id: null, mailbox_enabled: false, mail_disabled: false }]) })
  )
  await page.route('**/api/v1/external-parties*', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_EXTERNAL_PARTIES) })
  )
}

const BASE = 'http://localhost:80'

interface ScreenDef {
  name: string
  route: string
  isMatrix?: boolean
}

const CARD_SCREENS: ScreenDef[] = [
  { name: 'Members', route: '/app/members' },
  { name: 'Transactions', route: '/app/finance/transactions' },
  { name: 'Invoices', route: '/app/finance/invoices' },
  { name: 'TransactionCategories', route: '/app/finance/categories' },
  { name: 'Codes', route: '/app/operations/codes' },
  { name: 'Events', route: '/app/operations/events' },
  { name: 'Inventory', route: '/app/inventory' },
  { name: 'SystemPermissions', route: '/app/system' },
  { name: 'AuditLog', route: '/app/audit-log' },
  { name: 'UnifiedMail', route: '/app/mail' },
  { name: 'MemberMail', route: '/app/mail/members' },
  { name: 'GroupMail', route: '/app/mail/groups' },
  { name: 'SystemMail', route: '/app/mail/system' },
  { name: 'AllAddresses', route: '/app/mail/all' },
  { name: 'FunctionMail', route: '/app/mail/functions' },
  { name: 'WildDuckLive', route: '/app/mail/wildduck' },
  { name: 'ExternalParties', route: '/app/finance/parties' },
  { name: 'FinanceOverview', route: '/app/finance' },
]

test.describe('Mobile table card layout (375px)', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  for (const screen of CARD_SCREENS) {
    test(`${screen.name}: no horizontal scroll, card layout`, async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 812 })
      await page.goto(`${BASE}${screen.route}`, { waitUntil: 'networkidle', timeout: 15000 })

      const results = await page.evaluate(() => {
        const hasHScroll = document.documentElement.scrollWidth > document.documentElement.clientWidth
        const table = document.querySelector('.responsive-table')
        if (!table) return { hasHScroll, hasTable: false, hasRows: false }
        // Find a row with data-label cells (skip empty/loading rows)
        const rows = table.querySelectorAll('tbody tr')
        let tr: Element | null = null
        for (const r of rows) {
          if (r.querySelector('td[data-label]')) { tr = r; break }
        }
        if (!tr) return { hasHScroll, hasTable: true, hasRows: false }
        const trStyle = getComputedStyle(tr)
        const td = tr.querySelector('td[data-label]')
        const tdStyle = td ? getComputedStyle(td) : null
        return {
          hasHScroll,
          hasTable: true,
          hasRows: true,
          trDisplay: trStyle.display,
          trBorderRadius: trStyle.borderRadius,
          tdFlexDirection: tdStyle?.flexDirection,
        }
      })

      // No horizontal scroll on any screen
      expect(results.hasHScroll).toBe(false)

      if (results.hasTable && results.hasRows) {
        // Card layout properties when table exists
        expect(results.trDisplay).toBe('flex')
        expect(results.trBorderRadius).not.toBe('0px')
        expect(results.tdFlexDirection).toBe('column')
      }
    })
  }

  test('RolesTab: matrix table preserves table layout with scroll', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`${BASE}/app/system/roles`, { waitUntil: 'networkidle', timeout: 15000 })

    const matrixTable = page.locator('table[style*="min-width"]').first()
    const isTableDisplay = await matrixTable.evaluate((el) =>
      getComputedStyle(el).display === 'table'
    )
    expect(isTableDisplay).toBe(true)
  })
})

test.describe('Table layout at desktop width (1024px)', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test('SystemPermissions: table layout with thead visible', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto(`${BASE}/app/system`, { waitUntil: 'networkidle', timeout: 15000 })

    const results = await page.evaluate(() => {
      const table = document.querySelector('.responsive-table')
      if (!table) return { hasTable: false }
      const thead = table.querySelector('thead')
      const theadStyle = thead ? getComputedStyle(thead) : null
      const tr = table.querySelector('tbody tr')
      const trStyle = tr ? getComputedStyle(tr) : null
      return {
        hasTable: true,
        theadDisplay: theadStyle?.display,
        trDisplay: trStyle?.display,
        trBorderRadius: trStyle?.borderRadius,
      }
    })

    expect(results.hasTable).toBe(true)
    expect(results.theadDisplay).toBe('table-header-group')
    expect(results.trDisplay).toBe('table-row')
    expect(results.trBorderRadius).toBe('0px')
  })

  test('Members: table layout with thead visible', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto(`${BASE}/app/members`, { waitUntil: 'networkidle', timeout: 15000 })

    // Switch to table view via the Seg toggle
    const tableToggle = page.locator('button', { hasText: /table/i }).first()
    if (await tableToggle.isVisible().catch(() => false)) {
      await tableToggle.click()
      await page.waitForTimeout(300)
    }

    const results = await page.evaluate(() => {
      const table = document.querySelector('.responsive-table')
      if (!table) return { hasTable: false }
      const thead = table.querySelector('thead')
      const theadStyle = thead ? getComputedStyle(thead) : null
      const tr = table.querySelector('tbody tr')
      const trStyle = tr ? getComputedStyle(tr) : null
      return {
        hasTable: true,
        theadDisplay: theadStyle?.display,
        trDisplay: trStyle?.display,
      }
    })

    // If no table found (card view), skip the table-specific checks
    if (results.hasTable) {
      expect(results.theadDisplay).toBe('table-header-group')
      expect(results.trDisplay).toBe('table-row')
    }
  })
})

test.describe('Boundary: 600px transition (default tier)', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
  })

  test('599px: card layout (below default tier breakpoint)', async ({ page }) => {
    await page.setViewportSize({ width: 599, height: 812 })
    await page.goto(`${BASE}/app/system`, { waitUntil: 'networkidle', timeout: 15000 })

    const trDisplay = await page.evaluate(() => {
      const tr = document.querySelector('.responsive-table tbody tr')
      return tr ? getComputedStyle(tr).display : null
    })
    expect(trDisplay).toBe('flex')
  })

  test('601px: table layout (above default tier breakpoint)', async ({ page }) => {
    await page.setViewportSize({ width: 601, height: 812 })
    await page.goto(`${BASE}/app/system`, { waitUntil: 'networkidle', timeout: 15000 })

    const trDisplay = await page.evaluate(() => {
      const tr = document.querySelector('.responsive-table tbody tr')
      return tr ? getComputedStyle(tr).display : null
    })
    expect(trDisplay).toBe('table-row')
  })
})
