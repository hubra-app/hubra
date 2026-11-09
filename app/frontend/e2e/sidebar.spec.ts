import { expect, test, type Page } from '@playwright/test'
import { appUrl } from './env'

const sidebar = (page: Page) => page.locator('.mantine-AppShell-navbar')
const entry = (page: Page, path: string) => sidebar(page).locator(`a.nav-item[href$="${path}"]`)

async function openCustomize(page: Page) {
  // The pencil next to the first heading of the sidebar.
  await sidebar(page).getByTestId('nav-edit').click()
  return page.getByRole('dialog', { name: 'Seitenleiste anpassen' })
}

async function resetSidebar(page: Page) {
  const dialog = await openCustomize(page)
  const reset = dialog.getByRole('button', { name: 'Zurücksetzen' })
  if (await reset.isEnabled()) await reset.click()
  await dialog.getByRole('button', { name: 'Fertig' }).click()
}

test.describe('settings tabs', () => {
  test('roles and the audit log are tabs of Einstellungen', async ({ page }) => {
    await page.goto(appUrl('settings'))
    await expect(entry(page, '/app/audit-log')).toHaveCount(0)
    await expect(entry(page, '/app/system')).toHaveCount(0)

    for (const [name, path] of [
      ['Rollen', '/app/system'],
      ['Protokoll', '/app/audit-log'],
    ]) {
      await page.getByRole('tab', { name }).click()
      await expect(page).toHaveURL(new RegExp(`${path}$`))
      await expect(page.getByRole('heading', { level: 1, name: 'Einstellungen' })).toBeVisible()
      await expect(page.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true')
      await expect(entry(page, '/app/settings')).toHaveAttribute('data-active', 'true')
    }
  })
})

test.describe('Weitere', () => {
  test('lists only the pages that are not in the sidebar', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    await resetSidebar(page)
    await expect(sidebar(page).getByTestId('nav-more')).toHaveCount(0)
    await entry(page, '/app/more').click()
    await expect(page.getByRole('heading', { level: 1, name: 'Weitere' })).toBeVisible()
    await expect(entry(page, '/app/more')).toHaveAttribute('data-active', 'true')
    // No tabs across unrelated pages any more.
    await expect(page.getByRole('tab')).toHaveCount(0)
    // Everything is in the sidebar, so nothing repeats here.
    await expect(page.getByTestId('module-card')).toHaveCount(0)
    await expect(page.getByText('Alles ist in deiner Seitenleiste')).toBeVisible()
  })
})

test.describe('own sidebar', () => {
  test.afterEach(async ({ page }) => {
    await resetSidebar(page)
  })

  test('pinned entries move to Favoriten, hidden ones only show on Weitere', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    const dialog = await openCustomize(page)
    await dialog.getByRole('button', { name: 'Als Favorit anheften: Anlässe' }).click()
    await dialog.getByRole('button', { name: 'Unter Weitere verschieben: Finanzen' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()

    await expect(sidebar(page).getByText('Favoriten')).toBeVisible()
    await expect(sidebar(page).locator('a.nav-item').first()).toHaveAttribute(
      'href',
      /\/app\/operations\/events$/,
    )
    await expect(entry(page, '/app/finance')).toHaveCount(0)

    // Weitere has its card and only that one, and the Weitere row stands for
    // it in the sidebar.
    await entry(page, '/app/more').click()
    const cards = page.getByTestId('module-card')
    await expect(cards).toHaveCount(1)
    const card = cards.filter({ hasText: 'Finanzen' })
    await card.click()
    await expect(page).toHaveURL(/\/app\/finance$/)
    await expect(entry(page, '/app/more')).toHaveAttribute('data-active', 'true')

    // And the search finds it.
    await page.goto(appUrl('dashboard'))
    await page.getByPlaceholder(/suchen/i).fill('Finanz')
    await page.getByText('Seite', { exact: true }).first().click()
    await expect(page).toHaveURL(/\/app\/finance$/)

    // Saved on the account: a reload keeps it.
    await page.reload()
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(entry(page, '/app/finance')).toHaveCount(0)
  })

  test('own categories and renamed headings', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    let dialog = await openCustomize(page)
    // A new category starts empty with its name ready to type.
    await dialog.getByRole('button', { name: 'Neue Kategorie' }).click()
    const name = dialog.getByRole('textbox', { name: 'Name der Kategorie' })
    await name.fill('Vorstand')
    await name.press('Enter')
    await expect(dialog.getByText('Leer. Mit den Pfeilen')).toBeVisible()
    // Übersetzungen is the last entry above it: one step down moves it in.
    await dialog.getByRole('button', { name: 'Nach unten: Übersetzungen' }).click()
    // Rename a built-in heading.
    await dialog.getByRole('button', { name: 'Umbenennen: Verein', exact: true }).click()
    await name.fill('Mein Verein')
    await name.press('Enter')
    await dialog.getByRole('button', { name: 'Fertig' }).click()

    const section = (heading: string) =>
      sidebar(page).locator(`xpath=.//p[normalize-space()="${heading}"]/../..`)
    await expect(section('Vorstand').locator('a.nav-item')).toHaveAttribute(
      'href',
      /\/app\/translations$/,
    )
    await expect(section('Mein Verein').locator('a.nav-item').first()).toHaveAttribute(
      'href',
      /\/app\/dashboard$/,
    )

    // Removing the category puts its page back where it came from.
    await page.reload()
    dialog = await openCustomize(page)
    await dialog.getByRole('button', { name: 'Kategorie entfernen: Vorstand' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()
    await expect(sidebar(page).getByText('Vorstand', { exact: true })).toHaveCount(0)
    await expect(entry(page, '/app/translations')).toHaveCount(1)
  })

  test('the arrows move an entry into the next section', async ({ page }) => {
    await page.goto(appUrl('dashboard'))
    // The pencil next to the first heading opens the dialog.
    await sidebar(page).getByTestId('nav-edit').click()
    const dialog = page.getByRole('dialog', { name: 'Seitenleiste anpassen' })
    await dialog.getByRole('button', { name: 'Nach unten: Finanzen' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()
    // The section is the heading's box: its first entry is now Finanzen.
    const vereinsleben = sidebar(page).locator('xpath=.//p[normalize-space()="Vereinsleben"]/../..')
    await expect(vereinsleben.locator('a.nav-item').first()).toHaveAttribute(
      'href',
      /\/app\/finance$/,
    )
  })
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  const drawer = (page: Page) =>
    page.getByRole('dialog').filter({ has: page.locator('a.nav-item') })

  test('page tabs wrap instead of scrolling sideways', async ({ page }) => {
    await page.goto(appUrl('finance'))
    const list = page.locator('.hubra-tabs .mantine-Tabs-list').first()
    await expect(list).toBeVisible()
    const [scroll, client] = await list.evaluate((el) => [el.scrollWidth, el.clientWidth])
    expect(scroll).toBeLessThanOrEqual(client)
    await expect(page.getByRole('tab', { name: 'Einstellungen' })).toBeInViewport()
  })

  test('the phone menu reorders sidebar entries', async ({ page }) => {
    const menu = page.getByRole('button', { name: 'Menü', exact: true })
    const order = () =>
      drawer(page)
        .locator('a.nav-item')
        .evaluateAll((links) => links.map((a) => a.getAttribute('href')?.replace(/.*\/app\//, '')))
    const customize = async () => {
      // The pencil next to the first heading of the phone menu.
      await drawer(page).getByTestId('nav-edit').click()
      return page.getByRole('dialog', { name: 'Seitenleiste anpassen' })
    }

    await page.goto(appUrl('dashboard'))
    await menu.click()
    const before = await order()
    const at = before.indexOf('finance')
    expect(at).toBeGreaterThan(0)
    let dialog = await customize()
    await dialog.getByRole('button', { name: 'Nach oben: Finanzen' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()

    await menu.click()
    const after = await order()
    expect(after.indexOf('finance')).toBe(at - 1)
    expect(after[at]).toBe(before[at - 1])

    // Back to the default order.
    dialog = await customize()
    await dialog.getByRole('button', { name: 'Zurücksetzen' }).click()
    await dialog.getByRole('button', { name: 'Fertig' }).click()
  })
})
