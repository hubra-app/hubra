/**
 * Query keys of the club app, in one place.
 *
 * A key's first entry names the list, so invalidating `qk.members.all`
 * also refreshes every filtered or paged members query below it.
 */
export const qk = {
  modules: ['modules'] as const,
  myTenants: ['my-tenants'] as const,
  dashboard: ['dashboard-summary'] as const,

  events: ['events'] as const,
  polls: ['polls'] as const,
  posts: {
    all: ['posts'] as const,
    one: (id: string) => ['post', id] as const,
    comments: (id: string) => ['post-comments', id] as const,
  },
  invoices: {
    all: ['invoices'] as const,
    one: (id: string) => ['invoice', id] as const,
    mine: ['my-invoices'] as const,
  },
  applications: ['applications'] as const,
  groups: {
    all: ['groups'] as const,
    joinable: ['groups', 'joinable'] as const,
    mine: ['my-groups'] as const,
    members: (id: number | string) => ['group-members', id] as const,
  },
  members: {
    all: ['members'] as const,
    one: (id: string) => ['member', id] as const,
    search: (q: string) => ['members', 'search', q] as const,
  },
}
