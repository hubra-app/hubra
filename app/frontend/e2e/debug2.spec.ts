import { test, expect } from '@playwright/test'

const MOCK_USER = {
  id: 1, first_name: 'Test', last_name: 'Admin', name: 'Test Admin',
  email: 'admin@vollbuild.ch', public_email: 'admin@vollbuild.ch',
  tier: { name: 'Standard' }, roles: [{ name: 'Admin' }], status: 'active',
  tool_hours: 0, notes: null, avatar_color: '#fece2b',
  joined: '2024-01-01', last_seen: '2024-01-01T00:00:00',
}

const MOCK_GROUP_BACKEND = {
  id: 1, name: 'Werkstatt', lead_id: null, lead_name: null,
  description: null, color: null, icon_name: null, member_count: 3,
  sessions: null, tools: 0, is_default: false, wildduck_alias_id: null,
  mail_enabled: false, forwarding_enabled: false, allow_send_as: false,
}

const MOCK_MEMBER_BACKEND = {
  id: '1', name: 'Anna Huber', public_email: 'anna@vollbuild.ch',
  mailbox_enabled: false, forwarding_enabled: false, retention_days: 90, wildduck_id: null,
}

test('debug: navigate to /mail/members and inspect page', async ({ page }) => {
  const requests: string[] = []
  page.on('request', req => {
    if (req.url().includes('/api/')) requests.push(`${req.method()} ${req.url()}`)
  })

  // Register routes
  const emptyList = (r: import('@playwright/test').Route) => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  const emptyObj = (r: import('@playwright/test').Route) => r.fulfill({ status: 200, contentType: 'application/json', body: '{}' })

  await page.route('**/api/v1/**', emptyObj)
  await page.route('**/api/v1/auth/bootstrap-status', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ bootstrapped: true }) })
  )
  await page.route('**/api/v1/events**', emptyList)
  await page.route('**/api/v1/polls**', emptyList)
  await page.route('**/api/v1/invoices**', emptyList)
  await page.route('**/api/v1/notifications**', emptyList)
  await page.route('**/api/v1/applications**', emptyList)
  await page.route('**/api/v1/groups', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MOCK_GROUP_BACKEND]) })
  )
  await page.route('**/api/v1/mail/members', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [MOCK_MEMBER_BACKEND] }) })
  )
  await page.route('**/api/v1/mail/aliases', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [] }) })
  )
  await page.route('**/api/v1/dashboard/summary', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ stats: { activeMembers: 0, pendingApplications: 0, openInvoices: 0, upcomingEvents: 0 } }) })
  )

  // seedAuth
  await page.addInitScript(() => {
    localStorage.setItem('vb_access', 'smoke-test-token')
    localStorage.setItem('vb_refresh', 'smoke-test-refresh')
    sessionStorage.setItem('vollbuild_phase', 'app')
  })
  await page.route('**/api/v1/account/', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) })
  )

  await page.goto('/mail/members')
  await page.waitForTimeout(3000)

  const url = page.url()
  const mainText = await page.evaluate(() => (document.querySelector('main')?.innerText ?? 'NO MAIN').substring(0, 800))
  const hasTable = await page.locator('[data-testid="member-mail-table"]').count()
  const routeText = await page.evaluate(() => {
    // Try to get the breadcrumb text from the topbar
    const banner = document.querySelector('[role="banner"]')
    return banner?.innerText?.split('\n')[0] ?? 'no banner'
  })

  const windowState = await page.evaluate(() => ({
    href: window.location.href,
    pathname: window.location.pathname,
    sessionPhase: sessionStorage.getItem('vollbuild_phase'),
    hasAccessToken: !!localStorage.getItem('vb_access'),
    historyState: JSON.stringify(window.history.state),
  }))

  console.log('=== DEBUG ===')
  console.log('page.url():', url)
  console.log('window state:', JSON.stringify(windowState, null, 2))
  console.log('Has member-mail-table:', hasTable)
  console.log('Topbar text:', routeText)
  console.log('Main content (first 200):', mainText.substring(0, 200))
  console.log('API Requests:', requests.filter(r => r.includes('/api/v1')).join('\n'))

  // Don't actually assert, just log
  expect(url).toBeTruthy()
})
