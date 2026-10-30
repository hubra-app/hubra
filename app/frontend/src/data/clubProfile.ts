import { useQuery } from '@tanstack/react-query'
import { qk } from '@/data/keys'
import { getClubProfile } from '@/api/settings'

/** The club's name, look and banner (Settings > Verein), for every member. */
export function useClubProfile() {
  return useQuery({
    queryKey: qk.settings.clubProfile,
    queryFn: getClubProfile,
    staleTime: 5 * 60_000,
  })
}
