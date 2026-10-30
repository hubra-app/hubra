import type { MantineColorScheme, MantineColorSchemeManager } from '@mantine/core'
import { BASE, getCookie, hasTokens } from '@hubra/api-client'

/**
 * Light, dark or follow the browser, the same on every portal.
 *
 * The choice lives on the account (users.theme) and in the `hubra_theme`
 * cookie on the shared domain (.hubra.club): sign-in sets the cookie from
 * the account, and public/theme.js reads it before the first paint, so the
 * club app, manage, sign-in and join all open in the same scheme.
 */
const COOKIE = 'hubra_theme'
const SCHEMES: readonly MantineColorScheme[] = ['light', 'dark', 'auto']

function parse(value: string): MantineColorScheme | null {
  return (SCHEMES as readonly string[]).includes(value) ? (value as MantineColorScheme) : null
}

/** The scheme in the cookie, or null when none was chosen yet. */
export function readColorScheme(): MantineColorScheme | null {
  const fromCookie = parse(getCookie(COOKIE))
  if (fromCookie) return fromCookie
  // Before the cookie, the club app kept it in Mantine's localStorage key.
  try {
    return parse(localStorage.getItem('mantine-color-scheme-value') ?? '')
  } catch {
    return null
  }
}

function writeCookie(value: MantineColorScheme) {
  // The parent of the portal hosts (.hubra.club for app.hubra.club), as the
  // API sets it; host-only on localhost and bare domains.
  const labels = window.location.hostname.split('.')
  const parent = labels.length > 2 ? `; domain=.${labels.slice(1).join('.')}` : ''
  const secure = window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `${COOKIE}=${value}; Max-Age=31536000; path=/; SameSite=Lax${parent}${secure}`
}

/** Saves the choice on the account too, so other devices follow. */
function saveOnAccount(value: MantineColorScheme) {
  if (!hasTokens()) return
  fetch(`${BASE}/account/profile`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-TOKEN': getCookie('csrf_access_token'),
    },
    body: JSON.stringify({ theme: value }),
  }).catch(() => {
    // Offline: the cookie still holds it for this browser.
  })
}

let onFocus: (() => void) | null = null

/** Mantine's colour scheme store, backed by the shared cookie. */
export const colorSchemeManager: MantineColorSchemeManager = {
  get: (defaultValue) => readColorScheme() ?? defaultValue,
  set: (value) => {
    if (parse(getCookie(COOKIE)) === value) return
    writeCookie(value)
    saveOnAccount(value)
  },
  // Another portal may have changed it while this tab was in the background.
  subscribe: (onUpdate) => {
    onFocus = () => {
      const value = readColorScheme()
      if (value) onUpdate(value)
    }
    window.addEventListener('focus', onFocus)
  },
  unsubscribe: () => {
    if (onFocus) window.removeEventListener('focus', onFocus)
    onFocus = null
  },
  clear: () => writeCookie('auto'),
}
