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

  it('takes the club colours only when set', () => {
    const plain = brandTheme({})
    expect(plain.other?.bnbAccent).toEqual({ light: '#7441e0', dark: '#9f7cf8' })
    expect(plain.colors?.gold?.[6]).toBe('#ecbb00')
    const branded = brandTheme({ primary: '#0a7c3e', accent: '#ff0000', secondary: '#1a237e' })
    expect(branded.other?.bnbAccent.light).toBe('#0a7c3e')
    expect(branded.colors?.gold?.[6]).toBe('#ff0000')
    expect(branded.colors?.club2?.[6]).toBe('#1a237e')
    expect(branded.primaryColor).toBe('accent')
  })
})
