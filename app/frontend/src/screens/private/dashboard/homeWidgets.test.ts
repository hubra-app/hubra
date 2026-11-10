import { describe, expect, it } from 'vitest'
import { MY_HOME, OPTIONAL_HOME } from './widgets'

describe('built-in start pages', () => {
  it('names plugin widgets by their catalogue type (w:<contract>)', () => {
    for (const type of OPTIONAL_HOME) expect(type.startsWith('w:')).toBe(true)
    expect(MY_HOME.some((wd) => wd.type === 'w:booking.onsite_today')).toBe(true)
  })
})
