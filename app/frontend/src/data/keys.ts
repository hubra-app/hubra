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
  features: ['features'] as const,
  myTenants: ['my-tenants'] as const,
  dashboard: ['dashboard-summary'] as const,
  dashboards: ['dashboards'] as const,
  dashboardHome: ['dashboards', 'home'] as const,
  contractWidgets: ['dashboards', 'widgets'] as const,
  widgetData: (name: string, config: unknown) =>
    ['dashboards', 'widgets', name, config] as const,
  lookups: ['lookups'] as const,
  languages: ['languages'] as const,
  translations: (locale: string) => ['translations', locale] as const,
  translationSuggestions: ['translation-suggestions'] as const,
  notifications: ['notifications'] as const,
  changelog: (lang: string, reader?: string) => ['changelog', lang, reader ?? ''] as const,
  support: {
    all: ['support'] as const,
    mine: ['support', 'mine'] as const,
    case: (id: number) => ['support', 'case', id] as const,
    roadmap: ['support', 'roadmap'] as const,
  },

  account: {
    all: ['account'] as const,
    mailSettings: ['account', 'mail-settings'] as const,
    navPrefs: ['account', 'nav-prefs'] as const,
    plan: ['my-plan'] as const,
    fee: ['my-fee'] as const,
    leave: ['my-leave'] as const,
    directory: ['my-directory'] as const,
    privacy: ['my-privacy'] as const,
    notifications: ['my-notifications'] as const,
    mailAddresses: ['my-mail-addresses'] as const,
  },

  events: ['events'] as const,
  eventTemplates: ['event-templates'] as const,
  associationEvents: ['events', 'from-associations'] as const,
  memberClubs: ['federation', 'clubs'] as const,
  eventPending: (id: string) => ['events', id, 'pending'] as const,
  eventRoll: (id: string) => ['events', id, 'roll'] as const,
  eventRegistrations: (id: string) => ['events', id, 'registrations'] as const,
  eventParticipants: (id: string) => ['events', id, 'participants'] as const,
  attendance: ['attendance'] as const,
  trialsAll: ['trials'] as const,
  trials: (past: boolean) => ['trials', past] as const,
  myAttendance: ['attendance', 'me'] as const,
  attendanceOverview: (from: string, to: string, groupId: string) =>
    ['attendance', from, to, groupId] as const,
  polls: ['polls'] as const,
  pollProxy: (id: string) => ['poll-proxy', id] as const,
  posts: {
    all: ['posts'] as const,
    one: (id: string | undefined) => ['post', id] as const,
    comments: (id: string | undefined) => ['post-comments', id] as const,
    translation: ['post-translation'] as const,
    reads: (id: string | undefined) => ['post-reads', id] as const,
  },

  members: {
    all: ['members'] as const,
    one: (id: string | undefined) => ['member', id] as const,
    search: (q: string) => ['members', 'search', q] as const,
    list: (...filters: unknown[]) => ['members', 'list', ...filters] as const,
    invites: ['members', 'invites'] as const,
    stats: (on: string, year: number) => ['members', 'stats', on, year] as const,
    consents: (id: string) => ['member-consents', id] as const,
    fee: (id: string) => ['member-fee', id] as const,
  },
  applications: ['applications'] as const,
  poster: (kind: string, source: string) => ['poster', kind, source] as const,
  signupSources: ['signup-sources'] as const,
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
    feeAdjustments: ['fee-adjustments'] as const,
    paymentPlans: (tierId: unknown) => ['payment-plans', tierId] as const,
  },

  invoices: {
    all: ['invoices'] as const,
    one: (id: string | undefined) => ['invoice', id] as const,
    mine: ['my-invoices'] as const,
    member: (id: string | undefined) => ['invoices', 'member', id] as const,
    /** Fee run preview for a day; under 'invoices' so new invoices refresh it. */
    feeRun: (on: string) => ['invoices', 'fee-run', on] as const,
  },
  transactions: {
    all: ['transactions'] as const,
    recent: ['transactions', { pageSize: 5 }] as const,
    categories: ['transaction-categories'] as const,
    one: (id: string | undefined) => ['transactions', 'one', id] as const,
  },
  financeOverview: ['finance-overview'] as const,
  financeSummary: (year: number) => ['finance-summary', year] as const,
  recurring: ['finance-recurring'] as const,
  feeBasis: (preview: string) => ['finance-fee-basis', preview] as const,
  chart: ['finance-chart'] as const,
  fiscalYears: ['finance-years'] as const,
  annualAll: ['finance-annual'] as const,
  annual: (year: number) => ['finance-annual', year] as const,
  externalParties: ['external-parties'] as const,

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
    clubMfa: ['club-settings', 'mfa'] as const,
    supportAccess: ['support-access'] as const,
    bank: ['bank-settings'] as const,
    clubProfile: ['club-profile'] as const,
    domains: ['domains'] as const,
    backupKey: ['backup-key'] as const,
    apps: ['connected-apps'] as const,
    apiAccess: ['api-access'] as const,
    apiTokens: ['api-access', 'tokens'] as const,
    webhooks: ['webhooks'] as const,
    associations: ['associations'] as const,
    subscription: ['hubra-billing'] as const,
    subscriptionInvoices: ['hubra-billing', 'invoices'] as const,
    subscriptionContact: ['hubra-billing', 'contact'] as const,
    subscriptionCatalog: ['hubra-billing', 'catalog'] as const,
    subscriptionLimits: ['hubra-billing', 'limits'] as const,
    webhookDeliveries: (id: number) => ['webhooks', id, 'deliveries'] as const,
    signInApps: ['api-access', 'sign-in-apps'] as const,
    appConnection: (id: number) => ['connected-apps', id] as const,
    rolesPermissions: ['roles-permissions'] as const,
    roleScopes: (roleId: unknown) => ['roles-permissions', 'scopes', roleId] as const,
  },
  audit: {
    log: (page: number, action: unknown, pageSize: number) => ['audit-log', page, action, pageSize] as const,
    entry: (id: unknown) => ['audit-entry', id] as const,
    member: (id: string | undefined) => ['audit-log', 'member', id] as const,
    target: (type: string, id: string | undefined) => ['audit-log', 'target', type, id] as const,
  },

  /** What the header search looks through, loaded once someone uses it. */
  search: {
    members: ['search-members'] as const,
    groups: ['search-groups'] as const,
    plugin: ['search-plugin'] as const,
    audit: ['search-audit'] as const,
  },
}
