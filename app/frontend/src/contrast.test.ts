import { describe, expect, it } from 'vitest'
import { DEFAULT_THEME, mergeMantineTheme } from '@mantine/core'
import { accColors, contrastRatio, cssVariablesResolver, readableOn, textOn, theme } from '@hubra/ui'
import { brandTheme, colorScale } from './branding'

const WHITE = '#ffffff'
const DARK_SURFACE = '#19191c'
// Colours clubs actually pick, from very light to very dark.
const CLUB_COLOURS = ['#ffeb3b', '#f5d90a', '#00e5ff', '#7cfc00', '#ff9800', '#e53935', '#0a7c3e', '#1a237e', '#000000', '#ffffff', '#7441e0']

describe('contrast', () => {
  it('measures WCAG contrast', () => {
    expect(contrastRatio('#000000', WHITE)).toBeCloseTo(21, 0)
    expect(contrastRatio(WHITE, WHITE)).toBeCloseTo(1, 5)
  })

  it('picks dark or white text like the avatars do', () => {
    expect(textOn('#ffeb3b')).toBe('#1a1625')
    expect(textOn('#1a237e')).toBe(WHITE)
    expect(textOn('#7441e0')).toBe(WHITE)
    // CSS variables can't be measured: white, as before
    expect(textOn('var(--mantine-color-acc-4)')).toBe(WHITE)
    for (const c of CLUB_COLOURS) {
      // the better of the two; a mid red reaches only ~4.2 with either
      const other = textOn(c) === WHITE ? '#1a1625' : WHITE
      expect(contrastRatio(c, textOn(c))).toBeGreaterThanOrEqual(contrastRatio(c, other))
      expect(contrastRatio(c, textOn(c))).toBeGreaterThanOrEqual(4)
    }
  })

  it('leaves readable colours alone and fixes the rest', () => {
    expect(readableOn('#7441e0', [WHITE])).toBe('#7441e0')
    const ochre = readableOn('#ffeb3b', [WHITE])
    expect(contrastRatio(ochre, WHITE)).toBeGreaterThanOrEqual(4.5)
    const lightBlue = readableOn('#1a237e', [DARK_SURFACE])
    expect(contrastRatio(lightBlue, DARK_SURFACE)).toBeGreaterThanOrEqual(4.5)
  })
})

describe('club colour as text', () => {
  it.each(CLUB_COLOURS)('%s: text shades read on light and dark surfaces', (hex) => {
    const s = colorScale(hex)
    expect(s[6]).toBe(hex)
    // light mode: active menu item, tabs and eyebrows
    for (const shade of [7, 8, 9]) {
      expect(contrastRatio(s[shade], WHITE)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(s[shade], s[1])).toBeGreaterThanOrEqual(4.5)
    }
    // dark mode: Mantine's text shade 4, light buttons shade 3
    for (const shade of [3, 4]) {
      expect(contrastRatio(s[shade], DARK_SURFACE)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it.each(CLUB_COLOURS)('%s: links, light and outline buttons read in light mode', (hex) => {
    const t = mergeMantineTheme(DEFAULT_THEME, brandTheme(theme, { primary: hex, accent: hex }))
    const vars = cssVariablesResolver(t)
    for (const name of ['acc', 'gold']) {
      const ink = vars.light[`--mantine-color-${name}-text`]
      expect(contrastRatio(ink, WHITE)).toBeGreaterThanOrEqual(4.5)
      expect(vars.light[`--mantine-color-${name}-light-color`]).toBe(ink)
      expect(vars.light[`--mantine-color-${name}-outline`]).toBe(ink)
    }
    expect(vars.light['--mantine-color-anchor']).toBe('var(--mantine-color-acc-text)')
  })

  it.each(CLUB_COLOURS)('%s: filled buttons get readable text in both modes', (hex) => {
    const t = mergeMantineTheme(DEFAULT_THEME, brandTheme(theme, { primary: hex }))
    const vars = cssVariablesResolver(t)
    const acc = t.colors.acc
    // the fill is shade 6 in light mode and shade 4 in dark mode
    expect(contrastRatio(vars.light['--mantine-color-acc-contrast'], acc[6])).toBeGreaterThanOrEqual(4)
    expect(contrastRatio(vars.dark['--mantine-color-acc-contrast'], acc[4])).toBeGreaterThanOrEqual(4)
    // a fixed colour: --mantine-color-black turns light in dark mode
    expect(vars.dark['--mantine-color-acc-contrast']).toMatch(/^#/)
    const filled = t.variantColorResolver({ color: 'acc', theme: t, variant: 'filled' })
    expect(filled.color).toBe('var(--mantine-color-acc-contrast)')
  })

  it('keeps Hubra violet as it is', () => {
    const vars = cssVariablesResolver(mergeMantineTheme(DEFAULT_THEME, theme))
    expect(vars.light['--mantine-color-acc-text']).toBe(accColors[6])
    expect(contrastRatio(accColors[4], DARK_SURFACE)).toBeGreaterThanOrEqual(4.5)
  })
})
