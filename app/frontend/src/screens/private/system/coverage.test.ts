import { describe, expect, it } from 'vitest'
import { coverage, flatten, percent } from './coverage'

describe('coverage', () => {
  it('lists per source the keys a language lacks', () => {
    const texts = {
      'de-CH': flatten({ a: { b: 'Hallo', c: 'Tschüss' }, kasse: { x: 'Strich' } }),
      'en-GB': flatten({ a: { b: 'Hello', c: ' ' }, kasse: {} }),
    }
    const rows = coverage(texts, [{ id: 'kasse', keys: new Set(['kasse.x']) }])
    expect(rows.map((r) => r.id)).toEqual(['core', 'kasse'])
    expect(rows[0].missing).toEqual({ 'de-CH': [], 'en-GB': ['a.c'] })
    expect(rows[1].missing['en-GB']).toEqual(['kasse.x'])
    expect(percent(rows[0], 'en-GB')).toBe(50)
    expect(percent(rows[0], 'de-CH')).toBe(100)
  })

  it('leaves out plugins without texts', () => {
    const rows = coverage({ 'de-CH': { a: 'x' } }, [{ id: 'empty', keys: new Set() }])
    expect(rows.map((r) => r.id)).toEqual(['core'])
  })
})
