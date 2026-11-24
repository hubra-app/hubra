import { type MantineColorsTuple, type MantineThemeOverride, type VariantColorsResolver } from '@mantine/core'
import {
  accentScale,
  createBnbTheme,
  variantColorResolver as bnbVariantColorResolver,
  type Accent,
} from '@bitsandbricks/ui'
import tokens, { readableOn, WHITE } from '@bitsandbricks/tokens'
import { goldColors, pinkColors } from './colors'

// Hubra on the shared BitsAndBricks theme (@bitsandbricks/ui): the tokens
// give the greys, status colours, radii and controls; Hubra brings its
// accent, its fonts and the few colours only Hubra has (gold, pink, the
// club's own colours). The same theme serves the club app, manage, sign-in
// and support, so the four look like one product.

/** Hubra Violet: the light one reads on white, the dark one on the dark page. */
export const HUBRA_ACCENT = { light: '#7441e0', dark: '#9f7cf8' } as const

/** Hubra's own faces, self-hosted in ./fonts (fonts.css). */
export const HUBRA_FONTS = {
  sans: '"Hanken Grotesk", system-ui, sans-serif',
  mono: '"JetBrains Mono", ui-monospace, monospace',
  headings: '"Bricolage Grotesque", "Hanken Grotesk", system-ui, sans-serif',
}

const { light: LIGHT, dark: DARK } = tokens.neutrals

/**
 * A colour a club picked, as an accent for both schemes: unchanged where it
 * already reads as text (4.5:1) on the page and on cards, otherwise darkened
 * (light scheme) or lightened (dark scheme) just enough. A yellow club gets
 * ochre on white, a navy one light blue on the dark page.
 */
export function clubAccent(hex: string): { light: string; dark: string } {
  return {
    light: readableOn(hex, [WHITE, LIGHT.bg, LIGHT.surface]),
    dark: readableOn(hex, [DARK.bg, DARK.surface, DARK.raised]),
  }
}

const asVar = (value: string) => Array(10).fill(value) as unknown as MantineColorsTuple

// Hubra's code and its plugins (built and published separately) name
// colours the way Hubra always did: acc, green, orange, red. They now mean
// the shared accent and status colours, so screens and plugins keep working
// and get the shared look; new code uses accent, ok, warn and err.
const ALIASES: Record<string, string> = { acc: 'accent', green: 'ok', orange: 'warn', red: 'err' }

const variantColorResolver: VariantColorsResolver = (input) => {
  const name = typeof input.color === 'string' ? ALIASES[input.color] : undefined
  return bnbVariantColorResolver(name ? { ...input, color: name } : input)
}

/** The Hubra theme, in Hubra violet or in the club's own colour. */
export function hubraTheme(accent: Accent = HUBRA_ACCENT): MantineThemeOverride {
  return createBnbTheme({
    accent,
    fonts: HUBRA_FONTS,
    overrides: {
      variantColorResolver,
      colors: {
        acc: accentScale(accent),
        green: asVar('var(--bnb-ok)'),
        orange: asVar('var(--bnb-warn)'),
        red: asVar('var(--bnb-err)'),
        // Hubra's older names for the neutrals, kept for plugins.
        ink: [
          'var(--bnb-raised)',
          'var(--bnb-raised)',
          'var(--bnb-line)',
          'var(--bnb-muted)',
          'var(--bnb-muted)',
          'var(--bnb-muted)',
          'var(--bnb-fg)',
          'var(--bnb-fg)',
          'var(--bnb-fg)',
          'var(--bnb-fg)',
        ],
        surface: [
          'var(--bnb-surface)',
          'var(--bnb-raised)',
          'var(--bnb-raised)',
          'var(--bnb-line)',
          'var(--bnb-line)',
          'var(--bnb-faint)',
          'var(--bnb-faint)',
          'var(--bnb-muted)',
          'var(--bnb-muted)',
          'var(--bnb-fg)',
        ],
        line: asVar('var(--bnb-line)'),
        bg: asVar('var(--bnb-bg)'),
        // Signal Gold (the logo dot, 'new' and 'due' markers) and pink: Hubra's own.
        gold: goldColors as unknown as MantineColorsTuple,
        pink: pinkColors as unknown as MantineColorsTuple,
      },
      components: {
        Tabs: { defaultProps: { color: 'accent' } },
      },
    },
  })
}

/** Hubra violet, for the apps that don't take a club's colours. */
export const theme = hubraTheme()
