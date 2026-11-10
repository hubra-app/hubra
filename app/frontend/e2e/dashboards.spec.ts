import { expect, test, type Page } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

type Widget = { id: string; type: string; size: string; w?: number; h?: number }
type Board = { id: number; widgets: Widget[] }

/** A new own dashboard with three notes, opened in edit mode. */
async function openBoard(page: Page): Promise<Board> {
  await page.goto(appUrl('dashboard'))
  const note = (id: string, size: string) => ({
    id,
    type: 'note',
    size,
    config: { title: `Notiz ${id}`, text: `Text ${id}` },
  })
  const board = await api<Board>(page, 'POST', '/app/dashboards/', {
    name: unique('Raster'),
    widgets: [note('a', 's'), note('b', 's'), note('c', 'm')],
  })
  await page.goto(appUrl(`dashboard/d/${board.id}`))
  await page.getByRole('button', { name: 'Bearbeiten' }).click()
  await expect(page.locator('.hb-dash-grid.editing')).toBeVisible()
  return board
}

const saved = (page: Page, id: number) =>
  api<Board>(page, 'GET', `/app/dashboards/${id}`).then((b) => b.widgets)

const cell = (page: Page, id: string) => page.locator(`[data-widget-id="${id}"]`)

test.describe('dashboard grid', () => {
  test.use({ viewport: { width: 1400, height: 900 } })

  test('the corner resizes a widget in columns and rows', async ({ page }) => {
    const board = await openBoard(page)
    const a = cell(page, 'a')
    await expect(a).toHaveAttribute('data-w', '4')
    await expect(a).toHaveAttribute('data-h', 'auto')

    // With the keyboard: one column wider, one row taller than its content.
    const corner = a.getByRole('button', { name: 'Grösse ändern (Notiz)' })
    await corner.focus()
    await page.keyboard.press('ArrowRight')
    await expect(a).toHaveAttribute('data-w', '5')
    await expect.poll(async () => (await saved(page, board.id))[0].w).toBe(5)

    // By dragging: two columns wider and a few rows taller.
    const grid = await page.locator('.hb-dash-grid').boundingBox()
    const box = await corner.boundingBox()
    if (!grid || !box) throw new Error('no grid')
    const col = (grid.width - 11 * 16) / 12 + 16
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + 2 * col, box.y + 3 * 56, { steps: 8 })
    await page.mouse.up()
    await expect(a).toHaveAttribute('data-w', '7')
    await expect
      .poll(async () => (await saved(page, board.id))[0])
      .toMatchObject({
        w: 7,
        size: 'm',
      })
    const h = (await saved(page, board.id))[0].h
    expect(h).toBeGreaterThan(1)

    // Back to the height of its content.
    await a.getByRole('button', { name: 'Höhe nach Inhalt' }).click()
    await expect(a).toHaveAttribute('data-h', 'auto')
    await expect.poll(async () => (await saved(page, board.id))[0].h).toBeUndefined()
  })

  test('the grip moves a widget', async ({ page }) => {
    const board = await openBoard(page)
    // By dragging the first onto the third.
    const grip = cell(page, 'a').locator('.hb-dash-grip')
    const target = await cell(page, 'c').boundingBox()
    const from = await grip.boundingBox()
    if (!target || !from) throw new Error('no widgets')
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
    await page.mouse.down()
    await page.mouse.move(target.x + target.width / 2, target.y + target.height / 2, { steps: 10 })
    await page.mouse.up()
    await expect
      .poll(async () => (await saved(page, board.id)).map((w) => w.id))
      .toEqual(['b', 'c', 'a'])

    // With the keyboard: one back.
    await cell(page, 'a').locator('.hb-dash-grip').focus()
    await page.keyboard.press('ArrowLeft')
    await expect
      .poll(async () => (await saved(page, board.id)).map((w) => w.id))
      .toEqual(['b', 'a', 'c'])

    // The bin removes one.
    await cell(page, 'b').getByRole('button', { name: 'Entfernen' }).click()
    await expect
      .poll(async () => (await saved(page, board.id)).map((w) => w.id))
      .toEqual(['a', 'c'])
    await api(page, 'DELETE', `/app/dashboards/${board.id}`)
  })
})
