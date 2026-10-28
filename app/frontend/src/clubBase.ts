/**
 * Multi-club URLs are /<club>/app/…. The router runs below /<club>, so every
 * screen keeps using /app/… paths in both modes, and changing club reloads
 * the page under the other club's base.
 */
const match = window.location.pathname.match(/^\/([^/]+)\/app(?:\/|$)/)

/** The club named in the URL, or null (single-club install, /app/…, /). */
export const URL_CLUB: string | null = match && match[1] !== 'app' ? decodeURIComponent(match[1]) : null

/** BrowserRouter basename: /<club> on multi-club pages. */
export const ROUTER_BASENAME: string | undefined = URL_CLUB ? `/${match![1]}` : undefined

/** An in-app path (/app/…) as a path on this origin, with the club base. */
export function withBase(path: string): string {
  if (!ROUTER_BASENAME || path.startsWith(ROUTER_BASENAME + '/')) return path
  return ROUTER_BASENAME + path
}
