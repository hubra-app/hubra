import { useQuery } from '@tanstack/react-query'
import { useAuth, useData } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { listGroups } from '@/api/groups'

/**
 * Events, posts and polls can belong to a group. A role held for one group
 * only (the youth team's lead) manages that group's content: they create in
 * their groups and edit what is in them. `key` is the right in question, such
 * as `posts.posts.create`.
 */
export function useContentGroups(key: string) {
  const { hasPermission } = useAuth()
  const { moduleList } = useData()
  const mayGroups = moduleList.some((m) => m.code === 'groups')
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: mayGroups,
  })
  const clubWide = hasPermission(key)
  const ownGroups = clubWide ? groups : groups.filter((g) => hasPermission(key, g.id))
  const groupName = (id: string | null | undefined) =>
    id ? (groups.find((g) => g.id === id)?.name ?? null) : null
  return {
    mayGroups,
    groups,
    /** Holds `key` club-wide: may leave the group empty ("for everyone"). */
    clubWide,
    /** The groups the content may go to. */
    ownGroups,
    /** May act at all: club-wide or for at least one group. */
    canAny: clubWide || ownGroups.length > 0,
    /** The group a new item starts in: none, or the only one they manage. */
    defaultGroup: clubWide ? '' : (ownGroups[0]?.id ?? ''),
    groupName,
  }
}

export type ContentGroupScope = ReturnType<typeof useContentGroups>
