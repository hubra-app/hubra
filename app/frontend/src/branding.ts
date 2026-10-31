import { useSyncExternalStore } from 'react'
import { mergeThemeOverrides, type MantineColorsTuple, type MantineThemeOverride } from '@mantine/core'
import { mix, readableOn } from '@hubra/ui'
import { URL_CLUB } from '@/clubBase'

const WHITE = '#ffffff'

/**
 * The club's own colours (Settings > Verein > Erscheinungsbild). The shell
 * sets them once the club profile has loaded, and main.tsx builds the
 * Mantine theme from them, so buttons, links and the active menu item take
 * the club's colour instead of Hubra violet.
 *
 * primary → the `acc` scale (Mantine's primary colour)
 * accent → the `gold` scale (announcement banner, highlights)
 * secondary → the `club2` scale (the stripe under the top bar)
 */
export interface ClubColors {
  primary?: string | null
  secondary?: string | null
  accent?: string | null
}

const HEX = /^#[0-9a-f]{6}$/i
// Remembered per club so the next visit starts in the club's colours
// instead of flashing violet until the profile arrives.
const STORAGE_KEY = `hubra.branding.${URL_CLUB ?? ''}`

function readStored(): ClubColors {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ClubColors) : {}
  } catch {
    return {}
  }
}

let colors: ClubColors = readStored()
const listeners = new Set<() => void>()

function same(a: ClubColors, b: ClubColors) {
  return a.primary === b.primary && a.secondary === b.secondary && a.accent === b.accent
}

export function setClubColors(next: ClubColors): void {
  const clean: ClubColors = {
    primary: next.primary && HEX.test(next.primary) ? next.primary : null,
    secondary: next.secondary && HEX.test(next.secondary) ? next.secondary : null,
    accent: next.accent && HEX.test(next.accent) ? next.accent : null,
  }
  if (same(clean, colors)) return
  colors = clean
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(clean))
  } catch {
    // private mode: the colours still apply for this visit
  }
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useClubColors(): ClubColors {
  return useSyncExternalStore(subscribe, () => colors)
}

// The surfaces the club colour sits on as text: white cards and the page
// in light mode, the dark surface and its club-tinted fills (ui.css mixes
// 12% and 20% of shade 6 into it) in dark mode.
const DARK_SURFACE = '#19191c'
const DARK_SURFACE_2 = '#222226'

/**
 * A ten-shade Mantine scale with `hex` as shade 6, the shade the theme uses
 * for filled buttons in light mode (lighter shades towards 0, darker to 9).
 *
 * Shades 7 to 9 are the club colour as text in light mode (active menu
 * item, tabs, eyebrows) and shades 3 and 4 in dark mode, so those are
 * pushed darker or lighter until they read at 4.5:1, whatever colour the
 * club picked. A yellow club gets ochre text, a navy one light blue.
 */
export function colorScale(hex: string): MantineColorsTuple {
  const base = hex.toLowerCase()
  const tints = [0.92, 0.84, 0.68, 0.5, 0.32, 0.15].map((a) => mix(base, WHITE, a))
  const shades = [0.18, 0.36, 0.52].map((a) => mix(base, '#000000', a))
  const scale = [...tints, base, ...shades]

  const lightBgs = [WHITE, scale[0], scale[1]]
  scale[7] = readableOn(scale[7], lightBgs)
  scale[8] = readableOn(scale[8], lightBgs, 5.5)
  scale[9] = readableOn(scale[9], lightBgs, 7)

  const darkBgs = [DARK_SURFACE, DARK_SURFACE_2, mix(DARK_SURFACE, base, 0.2)]
  scale[4] = readableOn(scale[4], darkBgs)
  scale[3] = readableOn(scale[3], darkBgs, 5.5)
  return scale as unknown as MantineColorsTuple
}

/** The Hubra theme with the club's colours laid over it. */
export function brandTheme(base: MantineThemeOverride, club: ClubColors): MantineThemeOverride {
  const scales: Record<string, MantineColorsTuple> = {}
  if (club.primary) scales.acc = colorScale(club.primary)
  if (club.accent) scales.gold = colorScale(club.accent)
  if (club.secondary) scales.club2 = colorScale(club.secondary)
  if (Object.keys(scales).length === 0) return base
  return mergeThemeOverrides(base, { colors: scales })
}
