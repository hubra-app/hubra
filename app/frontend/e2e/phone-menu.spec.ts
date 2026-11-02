import { expect, test, type Locator, type Page } from '@playwright/test'
import { appUrl } from './env'

const drawer = (page: Page) => page.locator('.mantine-Drawer-content')
const card = (page: Page) => drawer(page).getByTestId('user-card')
const navViewport = (page: Page) => drawer(page).locator('.mantine-ScrollArea-viewport').first()

/** Fully on screen: not cut off by the bottom (or top) of the window. */
async function expectOnScreen(page: Page, el: Locator) {
  await expect(el).toBeVisible()
  const box = await el.boundingBox()
  const height = page.viewportSize()!.height
  expect(box).not.toBeNull()
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(height)
}

async function openMenu(page: Page) {
  await page.goto(appUrl('dashboard'))
  await page.getByRole('button', { name: 'Menü' }).click()
  await expect(drawer(page)).toBeVisible()
}

test.describe('phone menu account card', () => {
  // A small phone, so the nav is longer than the screen.
  test.use({ viewport: { width: 375, height: 600 }, hasTouch: true, isMobile: true })

  test('stays in view while the nav scrolls', async ({ page }) => {
    await openMenu(page)
    await expectOnScreen(page, card(page))
    // The menu takes the whole screen width.
    const box = await drawer(page).boundingBox()
    expect(box!.width).toBeCloseTo(page.viewportSize()!.width, 0)

    // Weitere open makes the list longer still.
    await drawer(page).getByTestId('nav-more').click()
    const vp = navViewport(page)
    expect(await vp.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)
    for (const top of [99999, 0]) {
      await vp.evaluate((el, y) => el.scrollTo(0, y), top)
      await expectOnScreen(page, card(page))
    }
  })

  test('opens the account menu on screen and folds it again', async ({ page }) => {
    await openMenu(page)
    const menu = drawer(page).getByTestId('user-menu')
    await expect(menu).toHaveCount(0)

    await card(page).tap()
    await expect(card(page)).toHaveAttribute('aria-expanded', 'true')
    await expectOnScreen(page, menu)
    await expectOnScreen(page, menu.getByRole('button', { name: 'Abmelden' }))
    await expectOnScreen(page, card(page))

    // A tap on the nav folds it; the phone menu stays open.
    await drawer(page).getByText('Vereinsleben').tap()
    await expect(menu).toHaveCount(0)
    await expect(drawer(page)).toBeVisible()

    // Escape folds it too.
    await card(page).tap()
    await expect(menu).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(menu).toHaveCount(0)
  })

  test('an account menu entry closes the phone menu', async ({ page }) => {
    await openMenu(page)
    await card(page).tap()
    await drawer(page).getByTestId('user-menu').getByRole('button', { name: 'Neuigkeiten' }).tap()
    await expect(drawer(page)).toHaveCount(0)
    const dialog = page.getByRole('dialog', { name: 'Neuigkeiten' })
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)

    // Next time the menu opens with the account menu folded.
    await page.getByRole('button', { name: 'Menü' }).click()
    await expectOnScreen(page, card(page))
    await expect(drawer(page).getByTestId('user-menu')).toHaveCount(0)
  })
})

test('the account menu only holds what the card and sidebar do not', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  const sidebar = page.locator('.mantine-AppShell-navbar')
  await sidebar.getByTestId('user-card').click()
  const menu = sidebar.getByTestId('user-menu')
  await expect(menu.getByRole('button')).toHaveText([
    'Mein Konto',
    'Neuigkeiten',
    'Problem melden',
    'Idee vorschlagen',
    'Abmelden',
  ])
  // The card already names who is signed in.
  await expect(menu.getByText('admin@demo.test')).toHaveCount(0)
})

test('the sidebar account menu closes on a click beside it', async ({ page }) => {
  await page.goto(appUrl('dashboard'))
  const sidebar = page.locator('.mantine-AppShell-navbar')
  await sidebar.getByTestId('user-card').click()
  await expect(sidebar.getByTestId('user-menu')).toBeVisible()
  await page.getByRole('heading', { level: 1 }).first().click()
  await expect(sidebar.getByTestId('user-menu')).toHaveCount(0)
})

test.describe('account settings on a phone', () => {
  test.use({ viewport: { width: 375, height: 667 }, hasTouch: true, isMobile: true })

  test('uses the same tabs as the other pages', async ({ page }) => {
    await page.goto(appUrl('account/settings'))
    const tabs = page.locator('.hubra-tabs')
    await expect(tabs.getByRole('tab', { name: 'Im Verein' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await tabs.getByRole('tab', { name: 'Mitgliedschaft' }).tap()
    await expect(page).toHaveURL(/\/app\/account\/settings\/membership$/)
    await expect(tabs.getByRole('tab', { name: 'Mitgliedschaft' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    // No dropdown in their place any more.
    await expect(page.getByRole('textbox', { name: 'Kontoeinstellungen' })).toHaveCount(0)
  })
})
