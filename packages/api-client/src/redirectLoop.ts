/**
 * Redirect-loop bookkeeping: plain functions of their inputs, so they can be
 * tested without a browser (see sso-frontend/tests/redirectLoop.test.ts).
 *
 * The portals (club app, SSO, manage) send each other back and forth when a
 * session is missing or not good enough. When two of them disagree about the
 * session, that turns into an endless loop. Every automatic redirect records
 * a hop; when too many pile up in a short time, it is a loop.
 *
 * A hop keeps only host and path: never the query (?redirect=, ?token=) or
 * the hash (#token= of mail links), so no secret ends up in the cookie or
 * the report.
 */

export interface Hop {
  /** Milliseconds since the epoch. */
  t: number
  /** host + path of the page that redirected. */
  from: string
  /** host + path of the target. */
  to: string
  /** Why the page redirected, a short code such as "anon" or "no-club". */
  why: string
}

/** Hops older than this are forgotten. */
export const WINDOW_MS = 20_000
/** This many automatic redirects within WINDOW_MS count as a loop. A normal
 * sign-in takes two to four (app → SSO → club picker → app, maybe the email
 * step); a loop makes about two a second, so it stops within a few seconds. */
export const LOOP_HOPS = 8
/** Hops kept (the cookie stays small). */
export const KEEP_HOPS = 10

const MAX_PART = 120

/** host + path of `url` (relative URLs resolve against `base`), no query or hash. */
export function stripUrl(url: string, base?: string): string {
  try {
    const u = new URL(url, base)
    return `${u.host}${u.pathname}`.slice(0, MAX_PART)
  } catch {
    return '?'
  }
}

/** The hops stored in the cookie value, oldest first; garbage reads as none. */
export function parseHops(raw: string | null | undefined): Hop[] {
  if (!raw) return []
  try {
    const data = JSON.parse(decodeURIComponent(raw)) as unknown
    if (!Array.isArray(data)) return []
    return data
      .filter(
        (h): h is Hop =>
          !!h &&
          typeof h === 'object' &&
          typeof (h as Hop).t === 'number' &&
          typeof (h as Hop).from === 'string' &&
          typeof (h as Hop).to === 'string' &&
          typeof (h as Hop).why === 'string',
      )
      .slice(-KEEP_HOPS)
  } catch {
    return []
  }
}

export function serializeHops(hops: Hop[]): string {
  return encodeURIComponent(JSON.stringify(hops.slice(-KEEP_HOPS)))
}

/** The hops still inside the window at `now`, with `hop` added. */
export function addHop(hops: Hop[], hop: Hop, now = hop.t): Hop[] {
  return [...hops.filter((h) => now - h.t <= WINDOW_MS && h.t <= now), hop].slice(-KEEP_HOPS)
}

/** True when the hops (already including the next one) make a loop. */
export function isLoop(hops: Hop[], now: number): boolean {
  return hops.filter((h) => now - h.t <= WINDOW_MS).length >= LOOP_HOPS
}

/** The chain as one line for a log or the error page: "a/x → b/y (why) → …". */
export function describeChain(hops: Hop[]): string {
  if (hops.length === 0) return ''
  const parts = [hops[0].from]
  for (const h of hops) parts.push(`${h.to} (${h.why})`)
  return parts.join(' → ')
}

/**
 * `url` resolved against `current` when it is a place the portals may send
 * people to, else null: http(s) only (never javascript: or data:), on the
 * same host, a host under the same parent domain (sso. / app. / manage. of
 * .hubra.club), one of `extraOrigins`, or localhost while developing.
 */
export function safeTarget(url: string, current: string, extraOrigins: string[] = []): string | null {
  let target: URL
  let here: URL
  try {
    here = new URL(current)
    target = new URL(url, here)
  } catch {
    return null
  }
  if (target.protocol !== 'https:' && target.protocol !== 'http:') return null
  if (target.username || target.password) return null
  const local = (h: string) => h === 'localhost' || h === '127.0.0.1'
  const labels = here.hostname.split('.')
  const parent = labels.length > 2 ? labels.slice(1).join('.') : here.hostname
  const ok =
    target.host === here.host ||
    (local(target.hostname) && local(here.hostname)) ||
    target.hostname === parent ||
    target.hostname.endsWith(`.${parent}`) ||
    extraOrigins.some((o) => {
      try {
        return new URL(o).origin === target.origin
      } catch {
        return false
      }
    })
  return ok ? target.href : null
}
