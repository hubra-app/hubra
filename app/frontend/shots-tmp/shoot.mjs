import { chromium } from 'playwright'
const APP = 'http://localhost:5173', SSO = 'http://localhost:5175'
const out = process.argv[2]
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2, locale: 'de-CH' })
const page = await ctx.newPage()
await page.goto(`${SSO}/login?redirect=${encodeURIComponent(APP + '/demo/app/dashboard')}`)
await page.getByLabel(/E-Mail/i).first().fill('admin@demo.test')
await page.getByLabel(/Passwort|Password/i).first().fill('Demo-Passwort-2026!')
await page.keyboard.press('Enter')
await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30000 }); await page.goto(`${APP}/demo/app/dashboard`); await page.waitForURL(`${APP}/demo/app/**`, { timeout: 30000 })
const api = async (method, path, data) => {
  const r = await page.evaluate(async ([method, path, data]) => {
    const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrf_access_token='))?.split('=')[1]
    const res = await fetch('/api/v1' + path, { method, credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf ?? '', 'X-Tenant-Slug': 'demo' }, body: data ? JSON.stringify(data) : undefined })
    return [res.status, await res.text()]
  }, [method, path, data])
  console.log(method, path, r[0], r[1].slice(0, 160))
}
if (process.argv[3] === 'seed') {
  await page.goto(`${APP}/demo/app/dashboard`); await page.waitForLoadState('networkidle')
  for (const [name, price] of [['Mineral', '2.00'], ['Bier', '4.00'], ['Kaffee', '1.50']]) await api('POST', '/app/kasse/products', { name, price, active: true })
  for (const id of [1, 2, 2, 3]) await api('POST', '/app/kasse/tab', { productId: id, qty: 1 })
}
const shot = async (path, name, w = 1280, h = 860) => {
  await page.setViewportSize({ width: w, height: h })
  await page.goto(`${APP}/demo${path}`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${out}/${name}.png` })
  console.log('shot', name, page.url())
}
await shot('/app/finance/tab-settle', '1-finance-tab-settle')
await shot('/app/finance/online-payments', '2-finance-online-payments')
await shot('/app/kasse/tab', '3-kasse-tab-member')
await shot('/app/payments?connected=1', '4-old-payments-link')
await shot('/app/finance/tab-settle', '5-finance-tab-settle-phone', 390, 844)
await browser.close()
