import { describe, expect, it } from 'vitest'
import { heightOf, move, resized, rowsFor, sizeFor, tabletWidth, widthOf, withSize } from './grid'

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
    expect([3, 4, 6, 12].map(tabletWidth)).toEqual([6, 6, 12, 12])
  })

  it('rounds content up to whole rows', () => {
    expect(rowsFor(1)).toBe(1)
    expect(rowsFor(40)).toBe(1)
    expect(rowsFor(41)).toBe(2)
    expect(rowsFor(heightOf(5))).toBe(5)
    expect(rowsFor(100_000)).toBe(24)
  })

  it('moves a widget to another place', () => {
    expect(move(['a', 'b', 'c', 'd'], 0, 2)).toEqual(['b', 'c', 'a', 'd'])
    expect(move(['a', 'b', 'c', 'd'], 3, 0)).toEqual(['d', 'a', 'b', 'c'])
    const same = ['a', 'b']
    expect(move(same, 1, 5)).toBe(same)
  })

  it('resizes in whole columns and rows', () => {
    // 12 columns of 50px with 16px gaps: 776px, a column step of 66px.
    expect(resized({ w: 6, h: 4 }, 66 * 2, 56 * 3, 776)).toEqual({ w: 8, h: 7 })
    expect(resized({ w: 6, h: 4 }, -1000, -1000, 776)).toEqual({ w: 2, h: 1 })
    expect(resized({ w: 6, h: 4 }, 500, 20, 776, false)).toEqual({ w: 6, h: 4 })
  })

  it('stores the grid size and the matching old size', () => {
    const w = { id: 'a', type: 'note', size: 'l' as const, config: {}, h: 3 }
    expect(withSize(w, 4, 6)).toMatchObject({ w: 4, h: 6, size: 's' })
    expect(withSize(w, 7, undefined)).not.toHaveProperty('h')
  })
})
