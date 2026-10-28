/**
 * The club's lists, loaded by the screens that show them.
 *
 * Each hook loads its list only while its module is on and the member may
 * read it (anything else answers 403), and only once a screen asks for it.
 * After a change, write the server's answer into the cache with
 * `useListCache` or invalidate the key; counts in the sidebar follow.
 */
import { useMemo } from 'react'
import { useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useAuth, useData } from '@/context/AppContext'
import { listEvents } from '@/api/events'
import { listPolls } from '@/api/polls'
import { listPosts } from '@/api/posts'
import { listInvoices } from '@/api/finance'
import { getDashboardSummary } from '@/api/dashboard'
import { listApplications } from '@/api/applications'
import { listGroups } from '@/api/groups'
import { getMyTenants } from '@/api/auth'
import type { ClubEvent, Invoice, Poll, Post } from '@/types'
import { qk } from './keys'

interface ListOptions {
  /** Hold the request back, e.g. until the search box is used. */
  enabled?: boolean
}

const EMPTY: never[] = []

/** Whether a list may be loaded: signed in, module on, permission held. */
function useMayLoad(module?: string, perm?: string) {
  const { authStatus, hasPermission } = useAuth()
  const { modules } = useData()
  if (authStatus !== 'authed') return false
  if (module && modules[module] !== true) return false
  return perm ? hasPermission(perm) : true
}

export function useEvents({ enabled = true }: ListOptions = {}) {
  const may = useMayLoad('events')
  const q = useQuery({ queryKey: qk.events, queryFn: () => listEvents(), enabled: enabled && may })
  return { ...q, events: q.data ?? (EMPTY as ClubEvent[]) }
}

export function usePolls({ enabled = true }: ListOptions = {}) {
  const may = useMayLoad('polls')
  const q = useQuery({ queryKey: qk.polls, queryFn: listPolls, enabled: enabled && may })
  return { ...q, polls: q.data ?? (EMPTY as Poll[]) }
}

export function usePosts({ enabled = true }: ListOptions = {}) {
  const may = useMayLoad('posts')
  const q = useQuery({ queryKey: qk.posts.all, queryFn: listPosts, enabled: enabled && may })
  return { ...q, posts: q.data ?? (EMPTY as Post[]) }
}

export function useInvoices({ enabled = true }: ListOptions = {}) {
  const may = useMayLoad('finance', 'finance.invoices.read')
  const q = useQuery({ queryKey: qk.invoices.all, queryFn: listInvoices, enabled: enabled && may })
  return { ...q, invoices: q.data ?? (EMPTY as Invoice[]) }
}

export function useDashboardSummary() {
  const may = useMayLoad()
  return useQuery({ queryKey: qk.dashboard, queryFn: getDashboardSummary, enabled: may })
}

export function useMyTenants() {
  const may = useMayLoad()
  const q = useQuery({ queryKey: qk.myTenants, queryFn: () => getMyTenants(), enabled: may })
  return q.data?.tenants ?? EMPTY
}

/** Ids of the events the signed-in member takes part in. */
export function useMyJoinedEvents() {
  const { events } = useEvents()
  const { currentUser } = useAuth()
  return useMemo(
    () =>
      new Set(
        events.filter((ev) => ev.attendees.includes(currentUser?.id ?? '')).map((ev) => ev.id),
      ),
    [events, currentUser],
  )
}

/** Option index the signed-in member chose, per poll id. */
export function useMyVotes() {
  const { polls } = usePolls()
  return useMemo(() => {
    const votes: Record<string, number> = {}
    for (const p of polls) if (p.myVote != null) votes[p.id] = p.myVote
    return votes
  }, [polls])
}

/** The numbers next to the sidebar entries. */
export function useNavCounts() {
  const { data: summary } = useDashboardSummary()
  const { polls } = usePolls()
  const mayApplications = useMayLoad(undefined, 'applications.applications.read')
  const { data: applications } = useQuery({
    queryKey: qk.applications,
    queryFn: listApplications,
    enabled: mayApplications,
  })
  const mayGroups = useMayLoad('groups')
  const { data: groups } = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: mayGroups,
  })
  return {
    members: summary?.stats?.activeMembers ?? 0,
    invoices: summary?.stats?.openInvoices ?? 0,
    applications: applications?.length ?? 0,
    groups: groups?.length ?? 0,
    polls: polls.filter((p) => p.status === 'open').length,
  }
}

/**
 * Write a change the server confirmed into a cached list, so the screen
 * shows it without loading the list again. Pass a key from `qk`, which
 * keeps its identity between renders.
 */
export function useListCache<T extends { id: string }>(key: QueryKey) {
  const queryClient = useQueryClient()
  return useMemo(() => {
    const update = (fn: (prev: T[]) => T[]) =>
      queryClient.setQueryData<T[]>(key, (prev) => fn(prev ?? []))
    return {
      prepend: (item: T) => update((prev) => [item, ...prev.filter((x) => x.id !== item.id)]),
      append: (item: T) => update((prev) => [...prev.filter((x) => x.id !== item.id), item]),
      replace: (item: T) => update((prev) => prev.map((x) => (x.id === item.id ? item : x))),
      patch: (id: string, fn: (item: T) => T) =>
        update((prev) => prev.map((x) => (x.id === id ? fn(x) : x))),
      remove: (id: string) => update((prev) => prev.filter((x) => x.id !== id)),
      get: () => queryClient.getQueryData<T[]>(key),
      set: (items: T[] | undefined) => queryClient.setQueryData(key, items),
      cancel: () => queryClient.cancelQueries({ queryKey: key }),
      invalidate: () => queryClient.invalidateQueries({ queryKey: key }),
    }
  }, [queryClient, key])
}
