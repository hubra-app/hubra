import { describe, expect, it } from 'vitest'
import { parseDate } from '@hubra/ui'

describe('parseDate', () => {
  it('reads Swiss and ISO dates', () => {
    expect(parseDate('11.11.2026')).toBe('2026-11-11')
    expect(parseDate('1.2.26')).toBe('2026-02-01')
    expect(parseDate(' 2026-03-05 ')).toBe('2026-03-05')
  })

  it('refuses dates that do not exist', () => {
    expect(parseDate('31.02.2026')).toBeNull()
    expect(parseDate('2026-13-01')).toBeNull()
    expect(parseDate('morgen')).toBeNull()
  })
})
