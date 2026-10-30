import { useSyncExternalStore } from 'react'
import { mergeThemeOverrides, type MantineColorsTuple, type MantineThemeOverride } from '@mantine/core'
import { URL_CLUB } from '@/clubBase'

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

function mix(hex: string, target: number, amount: number): string {
  const n = parseInt(hex.slice(1), 16)
  const channel = (shift: number) => {
    const c = (n >> shift) & 0xff
    return Math.round(c + (target - c) * amount)
  }
  return (
    '#' +
    [channel(16), channel(8), channel(0)].map((c) => c.toString(16).padStart(2, '0')).join('')
  )
}

/**
 * A ten-shade Mantine scale with `hex` as shade 6, the shade the theme uses
 * for filled buttons in light mode (lighter shades towards 0, darker to 9).
 */
export function colorScale(hex: string): MantineColorsTuple {
  const tints = [0.92, 0.84, 0.68, 0.5, 0.32, 0.15]
  const shades = [0.18, 0.36, 0.52]
  return [
    ...tints.map((a) => mix(hex, 255, a)),
    hex.toLowerCase(),
    ...shades.map((a) => mix(hex, 0, a)),
  ] as unknown as MantineColorsTuple
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
