// Text colours that stay readable on any colour a club or member picks.
// Contrast follows WCAG 2.1: 4.5:1 is the minimum for normal text.

const HEX = /^#?([0-9a-f]{6})$/i

export const INK = '#1a1625'
export const WHITE = '#ffffff'

function rgb(hex: string): [number, number, number] | null {
  const m = HEX.exec(hex.trim())
  if (!m) return null
  const n = parseInt(m[1], 16)
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
}

/** WCAG relative luminance, 0 (black) to 1 (white). */
export function luminance(hex: string): number {
  const c = rgb(hex)
  if (!c) return 0
  const [r, g, b] = c.map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrastRatio(a: string, b: string): number {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** `hex` moved `amount` (0 to 1) of the way towards `target`. */
export function mix(hex: string, target: string, amount: number): string {
  const a = rgb(hex) ?? [0, 0, 0]
  const b = rgb(target) ?? [0, 0, 0]
  return (
    '#' +
    a
      .map((c, i) => Math.round(c + (b[i] - c) * amount))
      .map((c) => c.toString(16).padStart(2, '0'))
      .join('')
  )
}

/**
 * Dark ink or white, whichever reads better on `bg`. Avatars, badges and
 * anything else filled with a picked colour use it for their text. Colours
 * that aren't hex (CSS variables) get white, the brand colours are dark.
 */
export function textOn(bg: string, dark = INK, light = WHITE): string {
  if (!rgb(bg)) return light
  return contrastRatio(bg, dark) >= contrastRatio(bg, light) ? dark : light
}

/**
 * `hex` as a text colour on every one of `backgrounds`: unchanged when it
 * already reaches `min`, otherwise darkened (light backgrounds) or lightened
 * (dark ones) just enough. A yellow club colour becomes a deep ochre on
 * white, a navy one a light blue on the dark surface.
 */
export function readableOn(hex: string, backgrounds: string[], min = 4.5): string {
  const ok = (c: string) => backgrounds.every((bg) => contrastRatio(c, bg) >= min)
  const start = hex.toLowerCase()
  if (ok(start)) return start
  const darkBgs = backgrounds.reduce((s, bg) => s + luminance(bg), 0) / backgrounds.length < 0.18
  const target = darkBgs ? WHITE : '#000000'
  for (let step = 1; step <= 20; step++) {
    const c = mix(start, target, step / 20)
    if (ok(c)) return c
  }
  return target
}
