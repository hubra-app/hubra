import type { Dashboard } from '@/api/dashboards'

export type Visibility = 'private' | 'club' | 'groups'
export type Sharing = { visibility: Visibility; groupIds: number[] }

/** How a dashboard is shared now, in the form's terms. */
export function sharingOf(d: Pick<Dashboard, 'shared' | 'groups'>): Sharing {
  if (!d.shared) return { visibility: 'private', groupIds: [] }
  const ids = (d.groups ?? []).map((g) => g.id)
  return ids.length ? { visibility: 'groups', groupIds: ids } : { visibility: 'club', groupIds: [] }
}

/** What the sharing endpoint takes for *s*. */
export function sharingBody(s: Sharing): { shared: boolean; groupIds: number[] } {
  return {
    shared: s.visibility !== 'private',
    groupIds: s.visibility === 'groups' ? s.groupIds : [],
  }
}

/** Whether *s* can be saved: "Gruppen" needs at least one group. */
export function sharingValid(s: Sharing): boolean {
  return s.visibility !== 'groups' || s.groupIds.length > 0
}
