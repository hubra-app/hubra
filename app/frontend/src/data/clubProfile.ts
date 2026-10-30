import { useQuery } from '@tanstack/react-query'
import { clubLogoUrl } from '@hubra/api-client'
import { useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { getClubProfile, type ClubProfile } from '@/api/settings'
import { URL_CLUB } from '@/clubBase'

// Remembered per club, so the logo and name show at once on the next visit
// instead of the Hubra mark until the profile arrives.
const STORAGE_KEY = `hubra.clubProfile.${URL_CLUB ?? ''}`

function readStored(): ClubProfile | undefined {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ClubProfile) : undefined
  } catch {
    return undefined
  }
}

async function fetchClubProfile(): Promise<ClubProfile> {
  const profile = await getClubProfile()
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Private mode or full storage: it just loads again next time.
  }
  return profile
}

/** The club's name, look and banner (Settings > Verein), for every member. */
export function useClubProfile() {
  const { authStatus, tenantSlug } = useAuth()
  return useQuery({
    // Per club, and only once signed in to it: asked earlier, the 403 stayed
    // cached and the logo was missing until a full reload.
    queryKey: [...qk.settings.clubProfile, tenantSlug],
    queryFn: fetchClubProfile,
    placeholderData: readStored,
    enabled: authStatus === 'authed',
    staleTime: 5 * 60_000,
    retry: 2,
  })
}

/** The club logo's URL (cached by the browser), or undefined without one. */
export function useClubLogo(): string | undefined {
  const { data } = useClubProfile()
  return clubLogoUrl(data?.slug, data?.logo_version)
}
