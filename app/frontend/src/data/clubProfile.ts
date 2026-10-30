import { useQuery } from '@tanstack/react-query'
import { clubLogoUrl } from '@hubra/api-client'
import { useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { getClubProfile } from '@/api/settings'

/** The club's name, look and banner (Settings > Verein), for every member. */
export function useClubProfile() {
  const { authStatus, tenantSlug } = useAuth()
  return useQuery({
    // Per club, and only once signed in to it: asked earlier, the 403 stayed
    // cached and the logo was missing until a full reload.
    queryKey: [...qk.settings.clubProfile, tenantSlug],
    queryFn: getClubProfile,
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
