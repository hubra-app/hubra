// Text colours that stay readable on any colour a club or member picks.
// The WCAG maths comes from @bitsandbricks/tokens; this file only adds what
// Hubra needs on top: colours that may be CSS variables, and text in a
// picked colour on the page in both schemes.
import tokens, {
  contrastRatio,
  INK,
  luminance,
  mix,
  readableOn,
  textOn as tokensTextOn,
  WHITE,
} from '@bitsandbricks/tokens'

export { contrastRatio, INK, luminance, mix, readableOn, WHITE }

const HEX = /^#?([0-9a-f]{6})$/i

/**
 * Dark ink or white, whichever reads better on `bg`. Avatars, badges and
 * anything else filled with a picked colour use it for their text. Colours
 * that aren't hex (CSS variables) get white, as before.
 */
export function textOn(bg: string): string {
  return HEX.test(bg.trim()) ? tokensTextOn(bg.trim()) : WHITE
}

// The dark-scheme card that category text sits on.
const DARK_SURFACE = tokens.neutrals.dark.surface

/**
 * Text in a picked colour (a tag, a tier, an event type) that reads on the
 * page in light and dark mode. Hex colours are darkened or lightened as
 * needed; CSS variables (the status ones) pass through, since they already
 * switch with the scheme.
 */
export function colorText(color: string): string {
  if (!HEX.test(color)) return color
  return `light-dark(${readableOn(color, [WHITE])}, ${readableOn(color, [DARK_SURFACE])})`
}

/** Fill, border and text for a tag or pill in `color` (hex or CSS variable). */
export function tagStyle(color: string): { backgroundColor: string; borderColor: string; color: string } {
  return {
    backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
    borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
    color: colorText(color),
  }
}
