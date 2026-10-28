/**
 * Where the login portal sends a signed-in visitor. Plain functions of their
 * inputs, so they can be tested without a browser.
 */

export interface AppUrls {
  /** The club app (app.hubra.club). */
  cos: string
  /** The manager portal (manage.hubra.club). */
  manage: string
}

/** Dashboard of one club in the club app (routes are /:tenantSlug/app/*). */
export function clubAppUrl(urls: AppUrls, tenantSlug: string): string {
  return `${urls.cos}/${encodeURIComponent(tenantSlug)}/app/dashboard`
}

// Parent domain of the club app (app.hubra.club -> hubra.club); any of its
// subdomains is a valid redirect target. Empty for localhost and bare hosts.
function appDomain(urls: AppUrls): string {
  try {
    const labels = new URL(urls.cos).hostname.split('.')
    return labels.length > 2 ? labels.slice(1).join('.') : ''
  } catch {
    return ''
  }
}

/**
 * The ?redirect= target if it is one we trust, else null.
 *
 * The bare club app (no /<club>/ in the path) counts as no target: it has no
 * club to show and sends the visitor straight back here, which looped
 * forever for someone who isn't in a club.
 */
export function validateRedirect(
  raw: string | null,
  urls: AppUrls,
  { dev = false }: { dev?: boolean } = {},
): string | null {
  if (!raw) return null
  let url: URL
  try {
    url = new URL(raw)
  } catch {
    return null
  }
  const cosOrigin = new URL(urls.cos).origin
  if (url.origin === cosOrigin && (url.pathname === '/' || url.pathname === '')) return null

  // Any local port is fine while developing; a build only trusts the
  // configured origins below (which may themselves be localhost URLs).
  if (dev && url.protocol === 'http:' && url.hostname === 'localhost') return raw
  const domain = appDomain(urls)
  if (url.protocol === 'https:' && domain && url.hostname.endsWith(`.${domain}`)) return raw
  // The configured app origins (set at container start for other domains).
  if ([cosOrigin, new URL(urls.manage).origin].includes(url.origin)) return raw
  return null
}

/**
 * Where to send a signed-in user: the ?redirect= deep link if there is one,
 * else null for the club picker (/clubs). Everyone lands there, whatever
 * their roles (one person can be a superadmin, a club owner and a member at
 * once); the picker offers the manager portal to those who have it.
 */
export function signedInTarget(redirect: string | null): string | null {
  return redirect
}
