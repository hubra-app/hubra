import { describe, expect, it } from 'vitest'
import { brandTheme, colorScale } from './branding'

describe('club colours', () => {
  it('builds a scale with the club colour as shade 6', () => {
    const scale = colorScale('#0A7C3E')
    expect(scale).toHaveLength(10)
    expect(scale[6]).toBe('#0a7c3e')
    // lighter towards 0, darker towards 9
    expect(parseInt(scale[0].slice(1, 3), 16)).toBeGreaterThan(parseInt(scale[5].slice(1, 3), 16))
    expect(parseInt(scale[9].slice(3, 5), 16)).toBeLessThan(0x7c)
  })

  it('replaces the primary and accent scales only when set', () => {
    const base = { primaryColor: 'acc', colors: { acc: colorScale('#7441e0') } }
    expect(brandTheme(base, {})).toBe(base)
    const branded = brandTheme(base, { primary: '#0a7c3e', accent: '#ff0000' })
    expect(branded.colors?.acc?.[6]).toBe('#0a7c3e')
    expect(branded.colors?.gold?.[6]).toBe('#ff0000')
    expect(branded.primaryColor).toBe('acc')
  })
})
