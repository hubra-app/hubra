import { useEffect } from 'react'
import { useMantineColorScheme, type MantineColorScheme } from '@mantine/core'
import {
  createColorSchemeManager,
  readColorScheme as readSharedColorScheme,
} from '@bitsandbricks/ui'
import { BASE, getCookie, hasTokens } from '@hubra/api-client'

/**
 * Light, dark or follow the browser, the same on every portal.
 *
 * The choice lives on the account (users.theme) and in the `hubra_theme`
 * cookie on the shared domain (.hubra.club): sign-in sets the cookie from
 * the account, and the theme script (index.html, from @bitsandbricks/ui)
 * reads it before the first paint, so the club app, manage, sign-in and
 * support all open in the same scheme.
 */
export const THEME_COOKIE = 'hubra_theme'

/** The scheme in the cookie, or null when none was chosen yet. */
export function readColorScheme(): MantineColorScheme | null {
  return readSharedColorScheme(THEME_COOKIE)
}

/** Saves the choice on the account too, so other devices follow. */
function saveOnAccount(value: MantineColorScheme) {
  if (!hasTokens()) return
  fetch(`${BASE}/global/account/profile`, {
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

/** Mantine's colour scheme store, backed by the shared cookie. */
export const colorSchemeManager = createColorSchemeManager({
  cookie: THEME_COOKIE,
  parentDomain: true,
  onSave: saveOnAccount,
})

/**
 * Sign-in sets the cookie from the account without a page load: take it
 * over when a page frame mounts.
 */
export function useSavedColorScheme() {
  const { colorScheme, setColorScheme } = useMantineColorScheme()
  useEffect(() => {
    const saved = readColorScheme()
    if (saved && saved !== colorScheme) setColorScheme(saved)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per frame, on mount
  }, [])
}
