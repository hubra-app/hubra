import { compactGrid, flowGrid, freeSpot, type GridBox } from '@bitsandbricks/ui'
import type { DashboardWidget, WidgetSize } from '@/api/dashboards'

/**
 * Hubra's side of the shared dashboard grid (DashboardGrid in
 * @bitsandbricks/ui): 12 columns, rows of ROW px with GAP px between them.
 * A widget has a spot (x, y) and spans `w` columns and `h` rows; without `h`
 * it is as tall as its content, measured and rounded up to whole rows.
 * Dashboards saved before the spot existed are laid out in their order once
 * (flowGrid) and keep the spot from their next save on.
 */
export const COLS = 12
export const ROW = 40
export const GAP = 16
export const MIN_W = 2
export const MAX_H = 24
/** Rows a widget takes before its content was measured. */
export const START_ROWS = 4

const WIDTH: Record<WidgetSize, number> = { s: 4, m: 6, l: 12 }

/** Columns *widget* spans on a wide screen. */
export function widthOf(widget: Pick<DashboardWidget, 'w' | 'size'>): number {
  return clampW(widget.w ?? WIDTH[widget.size] ?? 6)
}

/** The size a widget component is told, so it can show more when wide. */
export function sizeFor(w: number): WidgetSize {
  return w <= 4 ? 's' : w <= 8 ? 'm' : 'l'
}

export function clampW(w: number): number {
  return Math.max(MIN_W, Math.min(COLS, Math.round(w)))
}

export function clampH(h: number): number {
  return Math.max(1, Math.min(MAX_H, Math.round(h)))
}

/** Rows a block *px* high takes (a row is ROW, every further one adds GAP). */
export function rowsFor(px: number): number {
  return clampH(Math.ceil((px + GAP) / (ROW + GAP)))
}

/** The height in px of *rows* rows. */
export function heightOf(rows: number): number {
  return rows * ROW + (rows - 1) * GAP
}

/** A widget on the grid: its box, and whether its height is its content's. */
export type Placed = GridBox & { widget: DashboardWidget; auto: boolean }

/**
 * Where *widgets* sit: their saved spot, or (saved before spots) in their
 * order. *rows* are the measured content heights of widgets without `h`;
 * a widget measured empty (0) is left out. Every box floats up as far as
 * it goes, so a widget that grows pushes the ones below it down.
 */
export function layout(widgets: DashboardWidget[], rows: ReadonlyMap<string, number>): Placed[] {
  const shown = widgets.filter((wd) => rows.get(wd.id) !== 0)
  const box = (wd: DashboardWidget) => ({
    widget: wd,
    auto: wd.h === undefined,
    w: widthOf(wd),
    h: wd.h === undefined ? (rows.get(wd.id) ?? START_ROWS) : clampH(wd.h),
  })
  if (shown.every((wd) => wd.x === undefined || wd.y === undefined)) {
    return flowGrid(shown.map(box), COLS)
  }
  // Placed ones keep their spot; any without one goes into the first gap.
  const placed: Placed[] = []
  for (const wd of shown) {
    if (wd.x !== undefined && wd.y !== undefined) placed.push({ ...box(wd), x: wd.x, y: wd.y })
  }
  for (const wd of shown) {
    if (wd.x !== undefined && wd.y !== undefined) continue
    const b = box(wd)
    placed.push({ ...b, ...freeSpot(placed, b.w, b.h, COLS) })
  }
  return compactGrid(placed, COLS)
}

/**
 * The widgets to save from the grid's new *items*: spot and width for all,
 * the height only where it was set, or where the move changed it from what
 * was shown (a resize). In reading order, so older apps keep the order.
 */
export function toWidgets(items: Placed[], before: Placed[]): DashboardWidget[] {
  const was = new Map(before.map((p) => [p.widget.id, p]))
  const sane = compactGrid(
    items.map((p) => ({ ...p, w: clampW(p.w), h: clampH(p.h) })),
    COLS,
  )
  return [...sane]
    .sort((a, b) => a.y - b.y || a.x - b.x)
    .map((p) => {
      const old = was.get(p.widget.id)
      const keepAuto = p.auto && old !== undefined && old.h === p.h
      return withBox(p.widget, p, keepAuto ? undefined : p.h)
    })
}

/** *widget* at *box*, with its height *h* (undefined: its content's). */
export function withBox(
  widget: DashboardWidget,
  box: Pick<GridBox, 'x' | 'y' | 'w'>,
  h: number | undefined,
): DashboardWidget {
  const w = clampW(box.w)
  const next: DashboardWidget = {
    ...widget,
    x: Math.max(0, Math.min(COLS - w, box.x)),
    y: Math.max(0, box.y),
    w,
    size: sizeFor(w),
  }
  if (h === undefined) delete next.h
  else next.h = clampH(h)
  return next
}

/** Every widget with the spot it has in *placed* (hidden ones keep theirs). */
export function withSpots(widgets: DashboardWidget[], placed: Placed[]): DashboardWidget[] {
  const at = new Map(placed.map((p) => [p.widget.id, p]))
  return widgets.map((wd) => {
    const p = at.get(wd.id)
    return p ? withBox(wd, p, wd.h) : wd
  })
}
