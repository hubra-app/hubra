import { expect, test, type Page } from '@playwright/test'
import { appUrl } from './env'

const switcher = (page: Page) => page.getByTestId('club-switcher')
const menu = (page: Page) => page.getByTestId('club-switcher-menu')

/** Adds a made-up second club to the member's clubs, and lets a switch to it succeed. */
async function withSecondClub(page: Page) {
  await page.route('**/global/account/my-tenants', async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    body.tenants.push({
      tenant_id: 9999,
      tenant_slug: 'zz-other-club',
      tenant_name: 'Anderer Verein',
      member_id: 1,
      admin_level: null,
      logo_version: null,
    })
    await route.fulfill({ response: res, json: body })
  })
  await page.route('**/global/auth/switch-tenant', (route) =>
    route.fulfill({ status: 200, json: { ok: true } }),
  )
}

test('the top bar names the current club and lists the member’s clubs', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  await expect(switcher(page)).toBeVisible()
  const name = (await switcher(page).locator('.hubra-club-switcher-name').innerText()).trim()
  expect(name.length).toBeGreaterThan(0)

  await switcher(page).click()
  await expect(menu(page)).toBeVisible()
  // The current club is marked; finding another one goes to the club picker.
  await expect(menu(page).locator('[aria-current="true"]')).toContainText(name)
  await expect(
    menu(page).getByRole('menuitem', { name: 'Weiteren Verein finden' }),
  ).toHaveAttribute('href', /\/clubs$/)
  await page.keyboard.press('Escape')
  await expect(menu(page)).toHaveCount(0)
})

test('picking another club switches to it', async ({ page }) => {
  await withSecondClub(page)
  await page.goto(appUrl('dashboard'))
  await switcher(page).click()
  const switched = page.waitForRequest('**/global/auth/switch-tenant')
  await menu(page)
    .getByRole('menuitem', { name: /Anderer Verein/ })
    .click()
  expect((await switched).postDataJSON()).toEqual({ tenantSlug: 'zz-other-club' })
  await expect(page).toHaveURL(/\/zz-other-club\/app\/dashboard$/)
})

test('the account menu no longer lists the clubs', async ({ page }) => {
  await withSecondClub(page)
  await page.goto(appUrl('dashboard'))
  const sidebar = page.locator('.mantine-AppShell-navbar')
  await sidebar.getByTestId('user-card').click()
  await expect(sidebar.getByTestId('user-menu')).toBeVisible()
  await expect(sidebar.getByTestId('user-menu').getByText('Anderer Verein')).toHaveCount(0)
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 375, height: 667 }, hasTouch: true, isMobile: true })

  test('the switcher shows the club and its menu fits the screen', async ({ page }) => {
    await withSecondClub(page)
    await page.goto(appUrl('dashboard'))
    await expect(switcher(page)).toBeVisible()
    await switcher(page).tap()
    await expect(menu(page)).toBeVisible()
    const box = await menu(page).boundingBox()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(375)
    await expect(menu(page).getByRole('menuitem', { name: /Anderer Verein/ })).toBeVisible()
  })
})
