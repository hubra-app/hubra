import type { DashboardWidget, WidgetSize } from '@/api/dashboards'

/**
 * The dashboard grid: 12 columns, rows of ROW px with GAP px between them.
 * A widget spans `w` columns and `h` rows; without `h` it is as tall as its
 * content (rounded up to whole rows). Widgets fill the grid in their order,
 * a later small one moving up into a gap left by a wide one.
 */
export const COLS = 12
export const ROW = 40
export const GAP = 16
export const MIN_W = 2
export const MAX_H = 24

const WIDTH: Record<WidgetSize, number> = { s: 4, m: 6, l: 12 }

/** Columns *widget* spans on a wide screen. */
export function widthOf(widget: Pick<DashboardWidget, 'w' | 'size'>): number {
  return clampW(widget.w ?? WIDTH[widget.size] ?? 6)
}

/** The size a widget component is told, so it can show more when wide. */
export function sizeFor(w: number): WidgetSize {
  return w <= 4 ? 's' : w <= 8 ? 'm' : 'l'
}

/** Columns on a tablet (12 there too): a narrow widget half, the rest whole. */
export function tabletWidth(w: number): number {
  return w <= 4 ? 6 : COLS
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

/** *widgets* with the one at *from* moved to *to*. */
export function move<T>(widgets: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= widgets.length || to >= widgets.length) {
    return widgets
  }
  const next = [...widgets]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

/**
 * The size a resize ends at: the start size plus how far the pointer moved
 * (*dx*, *dy* in px) on a grid *gridWidth* px wide, in whole columns and rows.
 */
export function resized(
  start: { w: number; h: number },
  dx: number,
  dy: number,
  gridWidth: number,
  /** Off on a tablet or phone, where widths don't follow the 12 columns. */
  changeWidth = true,
): { w: number; h: number } {
  const colStep = (gridWidth - (COLS - 1) * GAP) / COLS + GAP
  const w = changeWidth ? clampW(start.w + dx / colStep) : start.w
  return { w, h: clampH(start.h + dy / (ROW + GAP)) }
}

/** *widget* with its grid size stored (and `size` kept for older apps). */
export function withSize(
  widget: DashboardWidget,
  w: number,
  h: number | undefined,
): DashboardWidget {
  const next: DashboardWidget = { ...widget, w: clampW(w), size: sizeFor(clampW(w)) }
  if (h === undefined) delete next.h
  else next.h = clampH(h)
  return next
}
