import { expect, test, type Page } from '@playwright/test'
import { api, unique } from './api'
import { appUrl } from './env'

type Widget = {
  id: string
  type: string
  size: string
  w?: number
  h?: number
  x?: number
  y?: number
}
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
  await expect(page.locator('.hb-dash.editing')).toBeVisible()
  return board
}

const saved = (page: Page, id: number) =>
  api<Board>(page, 'GET', `/app/dashboards/${id}`).then((b) => b.widgets)
const one = (page: Page, board: Board, id: string) =>
  saved(page, board.id).then((ws) => ws.find((w) => w.id === id))

const cell = (page: Page, id: string) => page.locator(`[data-widget-id="${id}"]`)
/** The grid's box around a widget, with the grip and the corner. */
const item = (page: Page, id: string) =>
  page.locator('.bnb-grid-item').filter({ has: cell(page, id) })

/** One column's step in px on the 12-column grid (16px gaps). */
async function colStep(page: Page) {
  const grid = await page.locator('.hb-dash-grid').boundingBox()
  if (!grid) throw new Error('no grid')
  return (grid.width + 16) / 12
}

test.describe('dashboard grid', () => {
  test.use({ viewport: { width: 1400, height: 900 } })

  test('the corner resizes a widget in columns and rows', async ({ page }) => {
    const board = await openBoard(page)
    const a = cell(page, 'a')
    await expect(a).toHaveAttribute('data-w', '4')
    await expect(a).toHaveAttribute('data-h', 'auto')

    // With the keyboard: Shift+→ on the grip, one column wider; still as tall as its content.
    await item(page, 'a').getByRole('button', { name: 'Widget verschieben' }).focus()
    await page.keyboard.press('Shift+ArrowRight')
    await expect(a).toHaveAttribute('data-w', '5')
    await expect.poll(async () => (await one(page, board, 'a'))?.w).toBe(5)
    await expect(a).toHaveAttribute('data-h', 'auto')

    // By dragging the corner: two columns wider and a few rows taller.
    const corner = await item(page, 'a').locator('.bnb-grid-corner').boundingBox()
    if (!corner) throw new Error('no corner')
    const col = await colStep(page)
    await page.mouse.move(corner.x + corner.width / 2, corner.y + corner.height / 2)
    await page.mouse.down()
    await page.mouse.move(corner.x + 2 * col, corner.y + 3 * 56, { steps: 8 })
    await page.mouse.up()
    await expect(a).toHaveAttribute('data-w', '7')
    await expect.poll(async () => await one(page, board, 'a')).toMatchObject({ w: 7, size: 'm' })
    expect((await one(page, board, 'a'))?.h).toBeGreaterThan(1)

    // Back to the height of its content.
    await a.getByRole('button', { name: 'Höhe nach Inhalt' }).click()
    await expect(a).toHaveAttribute('data-h', 'auto')
    await expect.poll(async () => (await one(page, board, 'a'))?.h).toBeUndefined()
  })

  test('the grip moves a widget', async ({ page }) => {
    const board = await openBoard(page)
    // By dragging the first four columns to the right, where b was: b makes room.
    const grip = await item(page, 'a').locator('.bnb-grid-grip').boundingBox()
    if (!grip) throw new Error('no grip')
    const col = await colStep(page)
    await page.mouse.move(grip.x + grip.width / 2, grip.y + grip.height / 2)
    await page.mouse.down()
    await page.mouse.move(grip.x + grip.width / 2 + 4 * col, grip.y + grip.height / 2, {
      steps: 10,
    })
    await page.mouse.up()
    await expect.poll(async () => await one(page, board, 'a')).toMatchObject({ x: 4, y: 0 })
    expect((await one(page, board, 'b'))?.y).toBeGreaterThan(0)

    // With the keyboard: one column back.
    await item(page, 'a').locator('.bnb-grid-grip').focus()
    await page.keyboard.press('ArrowLeft')
    await expect.poll(async () => (await one(page, board, 'a'))?.x).toBe(3)

    // The bin removes one.
    await cell(page, 'b').getByRole('button', { name: 'Entfernen' }).click()
    await expect
      .poll(async () => (await saved(page, board.id)).map((w) => w.id).sort())
      .toEqual(['a', 'c'])
    await api(page, 'DELETE', `/app/dashboards/${board.id}`)
  })
})
