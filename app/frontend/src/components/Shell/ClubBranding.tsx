import { useEffect } from 'react'
import { useClubProfile } from '@/data/clubProfile'
import { setClubColors } from '@/branding'
import { setDateFormat } from '@/format'

// The Hubra icons from index.html, to put back when a club removes its logo.
const defaultIcons = new Map<HTMLLinkElement, string>()

function setFavicon(logo: string | null) {
  document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]').forEach((link) => {
    if (!defaultIcons.has(link)) defaultIcons.set(link, link.href)
    if (logo) {
      link.removeAttribute('type')
      link.href = logo
    } else {
      link.href = defaultIcons.get(link)!
    }
  })
}

/** Puts the club's colours on the theme and its logo on the browser tab. */
export function ClubBranding() {
  const { data } = useClubProfile()
  // Before the pages below render, so their dates use the club's format.
  setDateFormat(data?.date_format)

  useEffect(() => {
    if (!data) return
    setClubColors({
      primary: data.primary_color,
      secondary: data.secondary_color,
      accent: data.accent_color,
    })
    setFavicon(data.logo)
  }, [data])

  return null
}
