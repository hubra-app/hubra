import { useSyncExternalStore } from 'react'
import {
  mergeThemeOverrides,
  type MantineColorsTuple,
  type MantineThemeOverride,
} from '@mantine/core'
import tokens from '@bitsandbricks/tokens'
import { clubAccent, hubraTheme, mix, readableOn } from '@hubra/ui'
import { URL_CLUB } from '@/clubBase'

const WHITE = '#ffffff'

/**
 * The club's own colours (Settings > Verein > Erscheinungsbild). The shell
 * sets them once the club profile has loaded, and main.tsx builds the
 * Mantine theme from them, so buttons, links and the active menu item take
 * the club's colour instead of Hubra violet.
 *
 * primary → the theme's accent (Mantine's primary colour, `accent`, and
 *   Hubra's older name for it, `acc`)
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

// The surfaces a club colour sits on as text in the dark scheme: the card,
// the raised fill, and a tint of the colour itself (light buttons, badges).
const DARK_SURFACE = tokens.neutrals.dark.surface
const DARK_SURFACE_2 = tokens.neutrals.dark.raised

/**
 * A ten-shade Mantine scale with `hex` as shade 6, for the club's second
 * and third colours (gold, club2): lighter shades towards 0, darker to 9.
 *
 * Shades 7 to 9 are the colour as text in light mode and shades 3 and 4 in
 * dark mode, so those are pushed darker or lighter until they read at
 * 4.5:1, whatever colour the club picked.
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

/**
 * The Hubra theme in the club's colours: its primary colour is the accent
 * (made readable as text in both schemes, see clubAccent), the other two
 * replace the gold and club2 scales. Hubra violet when the club has none.
 */
export function brandTheme(club: ClubColors): MantineThemeOverride {
  const base = hubraTheme(club.primary ? clubAccent(club.primary) : undefined)
  const scales: Record<string, MantineColorsTuple> = {}
  if (club.accent) scales.gold = colorScale(club.accent)
  if (club.secondary) scales.club2 = colorScale(club.secondary)
  if (Object.keys(scales).length === 0) return base
  return mergeThemeOverrides(base, { colors: scales })
}
