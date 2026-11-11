import { BASE } from '@hubra/api-client'

/**
 * The host of an image on another site, or null for one of this site, of
 * the Hubra API (club uploads), or data:/blob:. Loading another site's image
 * tells that site who reads the post and when (IP address, time), so those
 * wait for a click.
 */
export function foreignImageHost(
  src: string | undefined,
  here: string = window.location.href,
  api: string = BASE,
): string | null {
  if (!src) return null
  try {
    const url = new URL(src, here)
    if (url.protocol === 'data:' || url.protocol === 'blob:') return null
    const own = [new URL(here).origin, new URL(api, here).origin]
    return own.includes(url.origin) ? null : url.host
  } catch {
    return null
  }
}
