import { expect, test } from '@playwright/test'
import { appUrl } from './env'

// A made-up plugin whose screen and Finance tab throw, served in place of
// the API's answers, to check that a broken plugin stays contained.
const BUNDLE = `
window.HubraPluginHost.sdk.registerPlugin({
  id: 'e2e-broken',
  routes: [{ path: 'e2e-broken', module: 'e2e-broken', component: function () { throw new Error('boom') } }],
  tabs: [{ screen: 'finance', id: 'e2e-broken', module: 'e2e-broken', label: 'E2E kaputt',
           component: function () { throw new Error('boom') } },
         // The budgets plugin's id: the app puts it under "Budget & Beiträge".
         { screen: 'finance', id: 'budgets', module: 'e2e-broken', label: 'E2E Budgets',
           component: function () { return 'E2E-Budgetliste' } },
         { screen: 'finance', id: 'e2e-setup', group: 'setup', module: 'e2e-broken',
           label: 'E2E Einrichtung', component: function () { return 'E2E-Einrichtung' } }],
})
`

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/app/modules/', async (route) => {
    const res = await route.fetch()
    const modules = await res.json()
    modules.push({
      code: 'e2e-broken', name: 'E2E', description: '', dependsOn: [], required: false,
      defaultEnabled: false, enabled: true, switchedOn: true, allowed: true,
      missingDependencies: [], nav: [], settings: [], config: {}, configured: true,
      plugin: { id: 'e2e-broken', name: 'E2E', version: '1.0.0', author: '', trust: 'bundled', frontend: '1' },
    })
    await route.fulfill({ response: res, json: modules })
  })
  await page.route('**/plugins/e2e-broken/frontend.js*', (route) =>
    route.fulfill({ contentType: 'text/javascript', body: BUNDLE }),
  )
  page.on('console', () => {})
})

test("a plugin screen that throws shows a notice and leaves the app's frame working", async ({
  page,
}) => {
  await page.goto(appUrl('e2e-broken'))
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('a.nav-item').first()).toBeVisible()
  await expect(page.getByText('Etwas ist schiefgelaufen')).toHaveCount(0)
})

test('a plugin tab that throws leaves the rest of the screen working', async ({ page }) => {
  await page.goto(appUrl('finance/e2e-broken'))
  await expect(page.getByRole('heading', { level: 1, name: 'Finanzen' })).toBeVisible()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByRole('tab', { name: /Übersicht/ }).click().catch(async () => {
    await page.getByText('Übersicht').first().click()
  })
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('plugin finance tabs join the page tab they belong to', async ({ page }) => {
  const selected = (name: string) =>
    expect(page.getByRole('tab', { name, exact: true })).toHaveAttribute('aria-selected', 'true')

  await page.goto(appUrl('finance/budgets'))
  await expect(page.getByText('E2E-Budgetliste')).toBeVisible()
  await selected('Budget & Beiträge')
  await selected('E2E Budgets')
  await expect(page.getByRole('tab', { name: 'Beitragsgrundlage' })).toBeVisible()

  await page.goto(appUrl('finance/e2e-setup'))
  await expect(page.getByText('E2E-Einrichtung')).toBeVisible()
  await selected('Einstellungen')
  await selected('E2E Einrichtung')

  // A tab that names no group is a page tab of its own.
  await expect(
    page.getByRole('tablist', { name: 'Finanzen', exact: true }).getByRole('tab', { name: 'E2E kaputt' }),
  ).toBeVisible()
})
