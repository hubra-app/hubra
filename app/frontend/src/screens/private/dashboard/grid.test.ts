import { describe, expect, it } from 'vitest'
import { moveInGrid } from '@bitsandbricks/ui'
import type { DashboardWidget } from '@/api/dashboards'
import {
  heightOf,
  layout,
  rowsFor,
  sizeFor,
  START_ROWS,
  toWidgets,
  widthOf,
  withSpots,
} from './grid'

const note = (id: string, more: Partial<DashboardWidget> = {}): DashboardWidget => ({
  id,
  type: 'note',
  size: 's',
  config: {},
  ...more,
})
const boxes = (placed: ReturnType<typeof layout>) =>
  placed.map((p) => [p.widget.id, p.x, p.y, p.w, p.h])

describe('dashboard grid', () => {
  it('takes the width from w, else from the old size', () => {
    expect(widthOf({ size: 's' })).toBe(4)
    expect(widthOf({ size: 'm' })).toBe(6)
    expect(widthOf({ size: 'l' })).toBe(12)
    expect(widthOf({ size: 's', w: 9 })).toBe(9)
    expect(widthOf({ size: 's', w: 40 })).toBe(12)
  })

  it('tells widgets a size that matches their width', () => {
    expect([2, 4, 5, 8, 9, 12].map(sizeFor)).toEqual(['s', 's', 'm', 'm', 'l', 'l'])
  })

  it('rounds content up to whole rows', () => {
    expect(rowsFor(1)).toBe(1)
    expect(rowsFor(40)).toBe(1)
    expect(rowsFor(41)).toBe(2)
    expect(rowsFor(heightOf(5))).toBe(5)
    expect(rowsFor(100_000)).toBe(24)
  })

  it('lays out a dashboard saved before spots in its order', () => {
    const widgets = [note('a'), note('b', { size: 'm' }), note('c', { size: 'l', h: 2 })]
    const rows = new Map([
      ['a', 3],
      ['b', 5],
    ])
    expect(boxes(layout(widgets, rows))).toEqual([
      ['a', 0, 0, 4, 3],
      ['b', 4, 0, 6, 5],
      ['c', 0, 5, 12, 2],
    ])
  })

  it('keeps saved spots and floats widgets up', () => {
    const widgets = [note('a', { x: 6, y: 4, w: 6, h: 2 }), note('b', { x: 0, y: 9, w: 4 })]
    expect(boxes(layout(widgets, new Map()))).toEqual([
      ['a', 6, 0, 6, 2],
      ['b', 0, 0, 4, START_ROWS],
    ])
  })

  it('leaves out a widget that draws nothing', () => {
    const widgets = [note('a', { size: 'l' }), note('b', { size: 'l' })]
    const placed = layout(
      widgets,
      new Map([
        ['a', 0],
        ['b', 2],
      ]),
    )
    expect(boxes(placed)).toEqual([['b', 0, 0, 12, 2]])
  })

  it('puts a widget without a spot into the first gap', () => {
    const widgets = [note('a', { x: 0, y: 0, w: 6, h: 2 }), note('b', { w: 6, h: 2 })]
    expect(boxes(layout(widgets, new Map()))).toEqual([
      ['a', 0, 0, 6, 2],
      ['b', 6, 0, 6, 2],
    ])
  })

  it('saves spots, and a height only where it was set or resized', () => {
    const widgets = [note('a'), note('b', { h: 3 }), note('c')]
    const before = layout(
      widgets,
      new Map([
        ['a', 2],
        ['c', 4],
      ]),
    )
    expect(boxes(before)).toEqual([
      ['a', 0, 0, 4, 2],
      ['b', 4, 0, 4, 3],
      ['c', 8, 0, 4, 4],
    ])
    // c made taller and moved to the start; a and b only make room.
    const after = moveInGrid(moveInGrid(before, 2, { h: 6 }, 12), 2, { x: 0, y: 0 }, 12)
    const saved = toWidgets(after, before)
    expect(saved.map((w) => [w.id, w.x, w.y, w.w, w.h])).toEqual([
      ['c', 0, 0, 4, 6],
      ['b', 4, 0, 4, 3],
      ['a', 0, 6, 4, undefined],
    ])
  })

  it('keeps everyone’s spot when the list changes', () => {
    const widgets = [note('a'), note('b')]
    const placed = layout(
      widgets,
      new Map([
        ['a', 2],
        ['b', 2],
      ]),
    )
    const next = withSpots([...widgets, note('c')], placed)
    expect(next.map((w) => [w.id, w.x, w.y])).toEqual([
      ['a', 0, 0],
      ['b', 4, 0],
      ['c', undefined, undefined],
    ])
    expect(next[0]).not.toHaveProperty('h')
  })
})
