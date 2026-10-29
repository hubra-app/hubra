import { useDebouncedValue } from '@mantine/hooks'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { listMembers } from '@/api/members'
import { qk } from './keys'

const PAGE = 20

/**
 * Members whose name, email or phone match `search`, asked from the server
 * a page at a time instead of loading the whole club.
 */
export function useMemberSearch(search: string, { enabled = true } = {}) {
  const [q] = useDebouncedValue(search.trim(), 250)
  return useQuery({
    queryKey: qk.members.search(q),
    queryFn: () => listMembers({ search: q, pageSize: PAGE }),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  })
}
