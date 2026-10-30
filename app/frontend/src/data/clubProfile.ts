import { useQuery } from '@tanstack/react-query'
import { clubLogoUrl } from '@hubra/api-client'
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
  return useQuery({
    queryKey: qk.settings.clubProfile,
    queryFn: fetchClubProfile,
    placeholderData: readStored,
    staleTime: 5 * 60_000,
    // Unlike other lists, also retry a 401/403: right after sign-in or a
    // token refresh the first call can fail, and the shell would then show
    // no logo until a reload.
    retry: 2,
    retryDelay: (attempt) => 1000 * 2 ** attempt,
  })
}

/** The club's logo URL (browser-cached), or undefined without a logo. */
export function useClubLogo(): string | undefined {
  const { data } = useClubProfile()
  return clubLogoUrl(URL_CLUB, data?.logo_version)
}
