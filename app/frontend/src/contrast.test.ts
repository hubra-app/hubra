import { describe, expect, it } from 'vitest'
import { DEFAULT_THEME, mergeMantineTheme } from '@mantine/core'
import { cssVariablesResolver } from '@bitsandbricks/ui'
import tokens from '@bitsandbricks/tokens'
import { clubAccent, contrastRatio, HUBRA_ACCENT, readableOn, textOn, theme } from '@hubra/ui'
import { brandTheme, colorScale } from './branding'

const WHITE = '#ffffff'
const LIGHT = tokens.neutrals.light
const DARK = tokens.neutrals.dark
// Colours clubs actually pick, from very light to very dark.
const CLUB_COLOURS = [
  '#ffeb3b',
  '#f5d90a',
  '#00e5ff',
  '#7cfc00',
  '#ff9800',
  '#e53935',
  '#0a7c3e',
  '#1a237e',
  '#000000',
  '#ffffff',
  '#7441e0',
]

describe('contrast', () => {
  it('measures WCAG contrast', () => {
    expect(contrastRatio('#000000', WHITE)).toBeCloseTo(21, 0)
    expect(contrastRatio(WHITE, WHITE)).toBeCloseTo(1, 5)
  })

  it('picks dark or white text like the avatars do', () => {
    expect(textOn('#ffeb3b')).not.toBe(WHITE)
    expect(textOn('#1a237e')).toBe(WHITE)
    expect(textOn('#7441e0')).toBe(WHITE)
    // CSS variables can't be measured: white, as before
    expect(textOn('var(--mantine-color-acc-4)')).toBe(WHITE)
    for (const c of CLUB_COLOURS) {
      // a mid red reaches only ~4.2 with either
      expect(contrastRatio(c, textOn(c))).toBeGreaterThanOrEqual(4)
    }
  })

  it('leaves readable colours alone and fixes the rest', () => {
    expect(readableOn('#7441e0', [WHITE])).toBe('#7441e0')
    const ochre = readableOn('#ffeb3b', [WHITE])
    expect(contrastRatio(ochre, WHITE)).toBeGreaterThanOrEqual(4.5)
    const lightBlue = readableOn('#1a237e', [DARK.surface])
    expect(contrastRatio(lightBlue, DARK.surface)).toBeGreaterThanOrEqual(4.5)
  })
})

/** The accent the theme hands the tokens (theme.other.bnbAccent), per scheme. */
function accentOf(hex?: string) {
  const t = mergeMantineTheme(DEFAULT_THEME, brandTheme(hex ? { primary: hex } : {}))
  const vars = cssVariablesResolver(t)
  return {
    light: vars.light['--bnb-accent-light'],
    dark: vars.dark['--bnb-accent-dark'],
    onLight: vars.light['--bnb-on-accent-light'],
    onDark: vars.dark['--bnb-on-accent-dark'],
  }
}

describe('club colour as accent', () => {
  it.each(CLUB_COLOURS)('%s: reads as text on the page and on cards in both schemes', (hex) => {
    const a = accentOf(hex)
    for (const bg of [WHITE, LIGHT.bg, LIGHT.surface]) {
      expect(contrastRatio(a.light, bg)).toBeGreaterThanOrEqual(4.5)
    }
    for (const bg of [DARK.bg, DARK.surface, DARK.raised]) {
      expect(contrastRatio(a.dark, bg)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it.each(CLUB_COLOURS)('%s: filled buttons get readable text in both schemes', (hex) => {
    const a = accentOf(hex)
    expect(contrastRatio(a.onLight, a.light)).toBeGreaterThanOrEqual(4)
    expect(contrastRatio(a.onDark, a.dark)).toBeGreaterThanOrEqual(4)
  })

  it('maps Hubra’s older colour names to the shared ones', () => {
    const t = mergeMantineTheme(DEFAULT_THEME, theme)
    const acc = t.variantColorResolver({ color: 'acc', theme: t, variant: 'filled' })
    expect(acc.background).toBe('var(--bnb-accent)')
    expect(acc.color).toBe('var(--bnb-on-accent)')
    const red = t.variantColorResolver({ color: 'red', theme: t, variant: 'light' })
    expect(red.color).toContain('var(--bnb-err)')
    const green = t.variantColorResolver({ color: 'green', theme: t, variant: 'filled' })
    expect(green.background).toBe('var(--bnb-ok)')
  })

  it('keeps Hubra violet as it is', () => {
    expect(accentOf()).toMatchObject(HUBRA_ACCENT)
    expect(clubAccent('#7441e0').light).toBe('#7441e0')
    expect(contrastRatio(HUBRA_ACCENT.dark, DARK.surface)).toBeGreaterThanOrEqual(4.5)
  })
})

describe('club colour scales (gold, club2)', () => {
  it.each(CLUB_COLOURS)('%s: text shades read on light and dark surfaces', (hex) => {
    const s = colorScale(hex)
    expect(s[6]).toBe(hex)
    for (const shade of [7, 8, 9]) {
      expect(contrastRatio(s[shade], WHITE)).toBeGreaterThanOrEqual(4.5)
      expect(contrastRatio(s[shade], s[1])).toBeGreaterThanOrEqual(4.5)
    }
    for (const shade of [3, 4]) {
      expect(contrastRatio(s[shade], DARK.surface)).toBeGreaterThanOrEqual(4.5)
    }
  })
})
