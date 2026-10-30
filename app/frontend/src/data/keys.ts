/**
 * Query keys of the club app, in one place.
 *
 * A key's first entry names the list, so invalidating `qk.members.all`
 * also refreshes every filtered or paged members query below it. Use these
 * instead of writing keys by hand: two queries that share a key but load
 * different things hand each other the wrong data from the cache.
 * Plugins invalidate some of them by their strings (such as ['invoices']),
 * so keep the strings as they are.
 */
export const qk = {
  modules: ['modules'] as const,
  myTenants: ['my-tenants'] as const,
  dashboard: ['dashboard-summary'] as const,
  lookups: ['lookups'] as const,
  languages: ['languages'] as const,
  translations: (locale: string) => ['translations', locale] as const,
  translationSuggestions: ['translation-suggestions'] as const,
  notifications: ['notifications'] as const,
  changelog: ['changelog'] as const,

  account: {
    all: ['account'] as const,
    mailSettings: ['account', 'mail-settings'] as const,
    plan: ['my-plan'] as const,
    leave: ['my-leave'] as const,
    directory: ['my-directory'] as const,
  },

  events: ['events'] as const,
  eventPending: (id: string) => ['events', id, 'pending'] as const,
  polls: ['polls'] as const,
  pollProxy: (id: string) => ['poll-proxy', id] as const,
  posts: {
    all: ['posts'] as const,
    one: (id: string | undefined) => ['post', id] as const,
    comments: (id: string | undefined) => ['post-comments', id] as const,
  },

  members: {
    all: ['members'] as const,
    one: (id: string | undefined) => ['member', id] as const,
    search: (q: string) => ['members', 'search', q] as const,
    list: (...filters: unknown[]) => ['members', 'list', ...filters] as const,
  },
  applications: ['applications'] as const,
  leaveRequests: ['leave-requests'] as const,
  groups: {
    all: ['groups'] as const,
    joinable: ['groups', 'joinable'] as const,
    mine: ['my-groups'] as const,
    members: (id: number | string) => ['group-members', id] as const,
  },
  functions: ['functions'] as const,
  tiers: {
    all: ['tiers'] as const,
    members: (id: number | string) => ['tier-members', id] as const,
    costs: (tiers: unknown) => ['tier-costs', tiers] as const,
    paymentPlans: (tierId: unknown) => ['payment-plans', tierId] as const,
  },
  codes: ['codes'] as const,

  invoices: {
    all: ['invoices'] as const,
    one: (id: string | undefined) => ['invoice', id] as const,
    mine: ['my-invoices'] as const,
  },
  transactions: {
    all: ['transactions'] as const,
    recent: ['transactions', { pageSize: 5 }] as const,
    categories: ['transaction-categories'] as const,
  },
  financeOverview: ['finance-overview'] as const,
  externalParties: ['external-parties'] as const,

  inventory: ['inventory'] as const,
  keys: ['keys'] as const,
  bindings: {
    all: ['bindings'] as const,
    sources: (type: unknown) => ['binding-sources', type] as const,
    preview: (type: unknown, sourceId: unknown, attribute: unknown) =>
      ['binding-preview', type, sourceId, attribute] as const,
  },

  mail: {
    systemAddresses: ['system-addresses'] as const,
    aliases: (category: unknown, linkedId: unknown) => ['mail-aliases', category, linkedId] as const,
    addresses: ['mail-addresses'] as const,
    allAddresses: ['mail-all-addresses'] as const,
    fromWhitelist: (id: unknown) => ['from-whitelist', id] as const,
  },

  settings: {
    kv: ['kv-settings'] as const,
    club: ['club-settings'] as const,
    clubProfile: ['club-profile'] as const,
    domains: ['domains'] as const,
    rolesPermissions: ['roles-permissions'] as const,
  },
  audit: {
    log: (page: number, action: unknown, pageSize: number) => ['audit-log', page, action, pageSize] as const,
    entry: (id: unknown) => ['audit-entry', id] as const,
  },

  /** What the header search looks through, loaded once someone uses it. */
  search: {
    members: ['search-members'] as const,
    groups: ['search-groups'] as const,
    transactions: ['search-transactions'] as const,
    inventory: ['search-inventory'] as const,
    audit: ['search-audit'] as const,
  },
}
