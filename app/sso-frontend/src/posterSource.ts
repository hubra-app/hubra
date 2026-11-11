// A join or trial poster's QR code opens the club page with ?src=<tag>.
// The tag is kept for the tab (signing in or up in between drops the query)
// and sent with the request to join or the trial booking.

const key = (slug: string) => `hubra.src.${slug}`

/** The poster tag for *slug*: from the address, else the one seen before. */
export function posterSource(slug: string): string | undefined {
  const fromUrl = new URLSearchParams(window.location.search).get('src')
  try {
    if (fromUrl) sessionStorage.setItem(key(slug), fromUrl.slice(0, 60))
    return fromUrl?.slice(0, 60) ?? sessionStorage.getItem(key(slug)) ?? undefined
  } catch {
    return fromUrl?.slice(0, 60) ?? undefined
  }
}
