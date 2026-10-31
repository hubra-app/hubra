import {
  createTheme,
  defaultVariantColorsResolver,
  DEFAULT_THEME,
  parseThemeColor,
  rem,
  v8CssVariablesResolver,
  type CSSVariablesResolver,
  type VariantColorsResolver,
} from '@mantine/core'
import { accColors, goldColors, grayColors, pinkColors } from './colors'
import { readableOn, textOn, WHITE } from './contrast'

// Filled buttons, badges and checkboxes: Mantine picks their text from the
// light-mode shade and as var(--mantine-color-black), which ui.css turns
// light in dark mode, so a yellow club got light text on a yellow button in
// dark mode. Use the per-scheme --mantine-color-<name>-contrast instead,
// which cssVariablesResolver below works out from the shade actually shown.
const variantColorResolver: VariantColorsResolver = (input) => {
  const result = defaultVariantColorsResolver(input)
  if (input.variant !== 'filled' || input.autoContrast === false) return result
  const parsed = parseThemeColor({ color: input.color || input.theme.primaryColor, theme: input.theme })
  if (!parsed.isThemeColor) return { ...result, color: textOn(parsed.value) }
  if (parsed.shade === undefined) return { ...result, color: `var(--mantine-color-${parsed.color}-contrast)` }
  return { ...result, color: textOn(parsed.value) }
}

// Hubra brand theme (brand/README.md). The same file is used by the club app,
// the manager portal and the sign-in portal so the three look like one product.
export const theme = createTheme({
  primaryColor: 'acc',
  primaryShade: { light: 6, dark: 4 },
  // Text on filled buttons and badges: dark or white, whichever has more
  // contrast (0.179 is where the two are equal), the same rule as avatars.
  autoContrast: true,
  luminanceThreshold: 0.179,
  variantColorResolver,
  black: '#1a1625',

  breakpoints: {
    xs: '36em',
    sm: '48em',
    md: '62em',
    lg: '75em',
    xl: '90em',
    tab: '54.375em',
    nav: '68.75em',
  },

  colors: {
    // Dark mode: neutral greys, so only the club colour carries colour.
    dark: [
      '#ededef',
      '#c8c8ce',
      '#a8a8b0',
      '#7c7c85',
      '#45454c',
      '#2f2f34',
      '#222226',
      '#19191c',
      '#151517',
      '#111113',
    ],
    acc: accColors,
    gold: goldColors,
    pink: pinkColors,
    // Brand neutrals with a violet tint. Mantine uses gray for borders,
    // hover fills and dimmed text, so this one scale restyles all of them.
    gray: grayColors,
    bg: Array(10).fill('#f7f6fb') as unknown as typeof accColors,
    surface: [
      '#ffffff',
      '#f4f2f9',
      '#ebe8f2',
      '#dfdbe9',
      '#c8c1d8',
      '#b7b0c9',
      '#9d95b3',
      '#827a99',
      '#625a7a',
      '#2e2940',
    ],
    line: [
      '#e6e3ef',
      '#e6e3ef',
      '#e6e3ef',
      '#d6d2e3',
      '#d6d2e3',
      '#b7b0c9',
      '#b7b0c9',
      '#b7b0c9',
      '#b7b0c9',
      '#b7b0c9',
    ],
    ink: [
      '#f4f2f9',
      '#ebe8f2',
      '#dfdbe9',
      // Muted text: 4.6:1 on white and on the light greys (WCAG AA).
      '#706a85',
      '#5e5873',
      '#5e5873',
      '#2e2940',
      '#2e2940',
      '#1a1625',
      '#1a1625',
    ],
  },

  fontFamily: '"Hanken Grotesk", system-ui, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", ui-monospace, monospace',

  fontSizes: {
    xs: rem(12),
    sm: rem(14),
    md: rem(15),
    lg: rem(17),
    xl: rem(20),
  },

  headings: {
    fontFamily: `"Bricolage Grotesque", "Hanken Grotesk", ${DEFAULT_THEME.fontFamily}`,
    fontWeight: '700',
    sizes: {
      h1: { fontSize: rem(30), lineHeight: '1.15' },
      h2: { fontSize: rem(22), lineHeight: '1.25' },
      h3: { fontSize: rem(18), lineHeight: '1.3' },
      h4: { fontSize: rem(16), lineHeight: '1.35' },
    },
  },

  radius: {
    xs: '6px',
    sm: '8px',
    md: '10px',
    lg: '16px',
    xl: '20px',
  },

  shadows: {
    xs: '0 1px 2px rgba(26,22,37,.05)',
    sm: '0 1px 2px rgba(26,22,37,.05), 0 4px 12px -6px rgba(26,22,37,.08)',
    md: '0 2px 4px rgba(26,22,37,.04), 0 12px 28px -12px rgba(26,22,37,.16)',
    lg: '0 26px 64px -22px rgba(26,22,37,.28), 0 4px 14px -6px rgba(26,22,37,.15)',
    xl: '0 26px 64px -22px rgba(26,22,37,.28), 0 4px 14px -6px rgba(26,22,37,.15)',
  },

  defaultRadius: 'md',
  focusRing: 'auto',
  cursorType: 'pointer',

  components: {
    Button: {
      defaultProps: { radius: 'md', size: 'sm' },
      // Icons passed as children (not leftSection) still get breathing room.
      styles: { root: { fontWeight: 600 }, label: { gap: 6 } },
    },
    ActionIcon: {
      defaultProps: { radius: 'md', color: 'gray', variant: 'subtle' },
    },
    TextInput: { defaultProps: { radius: 'md', size: 'sm' } },
    PasswordInput: { defaultProps: { radius: 'md', size: 'sm' } },
    NumberInput: { defaultProps: { radius: 'md', size: 'sm' } },
    Textarea: { defaultProps: { radius: 'md', size: 'sm' } },
    Select: {
      defaultProps: { radius: 'md', size: 'sm', checkIconPosition: 'right' },
    },
    MultiSelect: { defaultProps: { radius: 'md', size: 'sm' } },
    InputWrapper: {
      styles: {
        label: { fontWeight: 600, marginBottom: 4 },
        description: { marginBottom: 6 },
      },
    },
    Modal: {
      defaultProps: {
        radius: 'lg',
        centered: true,
        padding: 'lg',
        overlayProps: { backgroundOpacity: 0.4, blur: 2 },
      },
      styles: {
        title: {
          fontFamily: `"Bricolage Grotesque", "Hanken Grotesk", sans-serif`,
          fontWeight: 700,
          fontSize: rem(19),
        },
      },
    },
    Drawer: {
      styles: {
        title: {
          fontFamily: `"Bricolage Grotesque", "Hanken Grotesk", sans-serif`,
          fontWeight: 700,
          fontSize: rem(19),
        },
      },
    },
    Paper: {
      defaultProps: { radius: 'lg', shadow: 'xs' },
    },
    Card: {
      defaultProps: { radius: 'lg', shadow: 'xs', withBorder: true },
    },
    Badge: {
      defaultProps: { radius: 'sm', size: 'md', variant: 'light' },
      styles: { root: { fontWeight: 600, textTransform: 'none' } },
    },
    Tabs: {
      defaultProps: { color: 'acc' },
      styles: { tab: { fontWeight: 600 } },
    },
    SegmentedControl: {
      defaultProps: { radius: 'md' },
      styles: { label: { fontWeight: 600 } },
    },
    Table: {
      defaultProps: {
        verticalSpacing: 'sm',
        horizontalSpacing: 'md',
        fontSize: 'sm',
        highlightOnHover: true,
      },
      styles: {
        th: {
          fontSize: rem(12),
          fontWeight: 600,
          color: 'var(--mantine-color-gray-7)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          whiteSpace: 'nowrap',
        },
      },
    },
    Tooltip: {
      defaultProps: { radius: 'sm', color: 'dark' },
    },
    Menu: {
      defaultProps: { radius: 'md', shadow: 'md' },
    },
    Popover: {
      defaultProps: { radius: 'md', shadow: 'md' },
    },
    Notification: {
      defaultProps: { radius: 'md' },
    },
    Alert: {
      defaultProps: { radius: 'md' },
      styles: { title: { fontWeight: 700 } },
    },
    Switch: {
      // Mantine 8+ puts a dot in the thumb; keep the plain thumb.
      defaultProps: { withThumbIndicator: false },
      styles: { label: { fontWeight: 500 } },
    },
  },
})

// Mantine 9 made the light variant solid colours, which turned avatars and
// light buttons grey on our tinted backgrounds. Keep the 8.x see-through tints.
//
// On top of that, text in the club colours (links, light and outline
// buttons, badges) gets a shade that is readable on the page: Mantine uses
// shade 6 as is, so a yellow club colour gave yellow text on white. The fill
// itself stays the club's colour; autoContrast picks its text.
export const cssVariablesResolver: CSSVariablesResolver = (t) => {
  const result = v8CssVariablesResolver(t)
  const shade = t.primaryShade as { light: number; dark: number }
  for (const [name, scale] of Object.entries(t.colors)) {
    if (!Array.isArray(scale) || !/^#[0-9a-f]{6}$/i.test(scale[shade.light])) continue
    result.light[`--mantine-color-${name}-contrast`] = textOn(scale[shade.light])
    result.dark[`--mantine-color-${name}-contrast`] = textOn(scale[shade.dark])
  }
  result.light['--mantine-primary-color-contrast'] = `var(--mantine-color-${t.primaryColor}-contrast)`
  result.dark['--mantine-primary-color-contrast'] = `var(--mantine-color-${t.primaryColor}-contrast)`
  for (const name of ['acc', 'gold']) {
    const scale = t.colors[name]
    if (!scale) continue
    const ink = readableOn(scale[6], [WHITE, scale[1]])
    result.light[`--mantine-color-${name}-text`] = ink
    result.light[`--mantine-color-${name}-light-color`] = ink
    result.light[`--mantine-color-${name}-outline`] = ink
    // Dark mode: Mantine draws outline buttons in shade 0, which ui.css
    // turns into a dark tint, so they vanished. Use the light text shade.
    result.dark[`--mantine-color-${name}-outline`] = `var(--mantine-color-${name}-3)`
  }
  result.light['--mantine-color-anchor'] = 'var(--mantine-color-acc-text)'
  return result
}
