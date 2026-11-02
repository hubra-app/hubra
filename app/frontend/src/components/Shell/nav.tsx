import {
  IconLayoutDashboard,
  IconUsers,
  IconBox,
  IconLayoutList,
  IconWallet,
  IconMail,
  IconSettings,
  IconUser,
  IconPackage,
  IconShield,
  IconGlobe,
  IconKey,
  IconLock,
  IconDevicesCog,
  IconLink,
  IconUserPlus,
  IconId,
  IconStairs,
  IconCalendar,
  IconChartBar,
  IconNews,
  IconDots,
} from '@tabler/icons-react'
import type { ReactNode } from 'react'
import type { ModuleInfo } from '@/api/modules'
import { pluginIcon } from '@/plugins'

export type NavItem = {
  path: string
  label: string
  icon: ReactNode
  count?: number
  /** What the count means, shown on hover. */
  countTitle?: string
  permKeys?: string[]
  /** The "Weitere" entry: the pages behind it, shown when it is opened. */
  children?: NavItem[]
}
export type NavSection = { label: string; items: NavItem[] }

export interface NavCounts {
  members: number
  applications: number
  groups: number
  polls: number
  invoices: number
}

export type SearchResult = {
  kind:
    | 'member'
    | 'group'
    | 'event'
    | 'invoice'
    | 'transaction'
    | 'inventory'
    | 'poll'
    | 'audit'
    | 'page'
  id: string
  label: string
  sub?: string
  path: string
}

export function initials(name: string): string {
  return (
    name
      .split(' ')
      .map((w) => w[0] ?? '')
      .join('')
      .toUpperCase()
      .slice(0, 2) || '?'
  )
}

// Dark or white initials, whichever reads better on the avatar colour.
export { textOn as contrastColor } from '@hubra/ui'

const NAV_ICONS: Record<string, ReactNode> = {
  dashboard: <IconLayoutDashboard size={24} />,
  users: <IconUsers size={24} />,
  box: <IconBox size={24} />,
  package: <IconPackage size={24} />,
  'layout-list': <IconLayoutList size={24} />,
  wallet: <IconWallet size={24} />,
  mail: <IconMail size={24} />,
  key: <IconKey size={24} />,
  lock: <IconLock size={24} />,
  link: <IconLink size={24} />,
  settings: <IconSettings size={24} />,
  shield: <IconShield size={24} />,
  'devices-cog': <IconDevicesCog size={24} />,
  globe: <IconGlobe size={24} />,
  user: <IconUser size={24} />,
  'user-plus': <IconUserPlus size={24} />,
  'id-badge': <IconId size={24} />,
  stairs: <IconStairs size={24} />,
  calendar: <IconCalendar size={24} />,
  'chart-bar': <IconChartBar size={24} />,
  news: <IconNews size={24} />,
}

/** The sidebar icon of a module's nav entry (built in, from its plugin, or a box). */
export function moduleNavIcon(name: string | undefined): ReactNode {
  if (!name) return <IconBox size={24} />
  return NAV_ICONS[name] ?? navIcon(name)
}

/** An icon a plugin brought along, or a box. */
function navIcon(name: string): ReactNode {
  const Icon = pluginIcon(name)
  return Icon ? <Icon size={24} /> : <IconBox size={24} />
}

const SECTION_ORDER = ['favourites', 'workspace', 'activities', 'operations', 'system', 'me']

/** Where the "Weitere" entry lists the pages that have no sidebar row. */
export const MORE_PATH = '/app/more'

/** Sections a person can move entries between (besides "Weitere"). */
const MOVABLE_SECTIONS = ['workspace', 'activities', 'operations', 'system']

/**
 * The person's own sidebar: entries pinned to the top (in this order), entries
 * put under "Weitere" (`hidden`), the order of entries, and entries moved to
 * another section than their module's.
 */
export type NavPrefs = {
  pinned: string[]
  hidden: string[]
  order?: string[]
  sections?: Record<string, string>
}
const NO_PREFS: NavPrefs = { pinned: [], hidden: [], order: [], sections: {} }

/** One group of entries in the customise dialog, as the sidebar shows them. */
export type NavGroup = { section: string; label: string; items: NavItem[] }

/** Where each entry sits by default, before the person moved it. */
export type NavHomes = Record<string, string>

type NavEntry = { item: NavItem; section: string }

/** Sidebar entries come from the modules that are on for the active club. */
function navEntries(
  c: NavCounts,
  t: (key: string, params?: Record<string, unknown>) => string,
  modules: ModuleInfo[],
): NavEntry[] {
  const counts: Record<string, number> = {
    '/app/members': c.members,
    '/app/members/applications': c.applications,
    '/app/groups': c.groups,
  }
  const items = modules
    .filter((m) => m.enabled)
    .flatMap((m) => m.nav.map((item) => ({ item, plugin: !!m.plugin })))
    .sort((a, b) => a.item.order - b.item.order)
  const entries: NavEntry[] = []
  const seenGroups = new Set<string>()
  const tabPerms: { parent: string; perms: string[] }[] = []
  for (const { item, plugin } of items) {
    // Modules shown as tabs of one screen share a single entry.
    if (item.group) {
      if (seenGroups.has(item.group)) continue
      seenGroups.add(item.group)
    }
    // Sub-pages are tabs on their parent's screen, not sidebar rows; the
    // parent stays visible to anyone who may open one of its tabs.
    if (item.parent) {
      tabPerms.push({ parent: item.parent, perms: item.perms })
      continue
    }
    entries.push({
      item: {
        path: item.path,
        label: t(item.labelKey),
        icon: NAV_ICONS[item.icon] ?? navIcon(item.icon),
        count: counts[item.path] || undefined,
        countTitle:
          item.path === '/app/members'
            ? t('shell.nav.activeMembersCount', { count: counts[item.path] })
            : undefined,
        permKeys: item.perms.length ? item.perms : undefined,
      },
      // A plugin's own pages wait under "Weitere" until someone pins them.
      section: plugin && item.section === 'workspace' ? 'more' : item.section,
    })
  }
  for (const { parent, perms } of tabPerms) {
    const host = entries.find((e) => e.item.path === parent)?.item
    if (host?.permKeys && perms.length) host.permKeys = [...host.permKeys, ...perms]
  }
  return entries
}

/**
 * The sidebar a person sees: what they may open, their pinned entries on top
 * as "Favoriten", entries in the sections they put them in, and everything
 * else under "Weitere". `more` lists those pages; the sidebar shows one
 * "Weitere" entry that opens to list them.
 */
export function buildNav(
  c: NavCounts,
  t: (key: string, params?: Record<string, unknown>) => string,
  modules: ModuleInfo[],
  hasPerm: (key: string) => boolean = () => true,
  prefs: NavPrefs = NO_PREFS,
): {
  nav: NavSection[]
  more: NavItem[]
  customizable: NavItem[]
  groups: NavGroup[]
  homes: NavHomes
} {
  const visible = navEntries(c, t, modules).filter(
    ({ item }) => !item.permKeys || item.permKeys.some(hasPerm),
  )
  // The person's own order; entries they never moved (new modules, say) keep
  // the default order after the ones they placed.
  const order = prefs.order ?? []
  const rankOf = (path: string) => {
    const i = order.indexOf(path)
    return i < 0 ? Number.MAX_SAFE_INTEGER : i
  }
  const hidden = new Set(prefs.hidden)
  const moved = prefs.sections ?? {}
  const homes: NavHomes = {}
  const placed = visible.map(({ item, section }, i) => {
    homes[item.path] = section
    let where = section
    if (section !== 'me') {
      if (hidden.has(item.path)) where = 'more'
      else if (MOVABLE_SECTIONS.includes(moved[item.path])) where = moved[item.path]
    }
    return { item, section: where, i }
  })
  const entries = placed
    .sort((a, b) => rankOf(a.item.path) - rankOf(b.item.path) || a.i - b.i)
    .map(({ item, section }) => ({ item, section }))
  const pinned = prefs.pinned.filter((path) =>
    entries.some((e) => e.item.path === path && e.section !== 'me'),
  )
  const sections = new Map<string, NavItem[]>()
  const add = (section: string, item: NavItem) =>
    sections.set(section, [...(sections.get(section) ?? []), item])
  const more: NavItem[] = []
  for (const path of pinned) add('favourites', entries.find((e) => e.item.path === path)!.item)
  for (const { item, section } of entries) {
    if (pinned.includes(item.path)) continue
    if (section === 'more') more.push(item)
    else add(section, item)
  }
  if (more.length > 0) {
    add('operations', {
      path: MORE_PATH,
      label: t('shell.nav.more'),
      icon: <IconDots size={24} />,
      children: more,
    })
  }
  const rank = (section: string) => SECTION_ORDER.indexOf(section) + 1 || 99
  const nav = [...sections.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([section, list]) => ({
      label: t(`shell.sections.${section}`),
      items: list,
    }))
  // In sidebar order, with the "Weitere" pages last.
  const ordered = entries
    .filter((e) => e.section !== 'me')
    .map((e, i) => ({ e, i }))
    .sort((a, b) => rank(a.e.section) - rank(b.e.section) || a.i - b.i)
    .map(({ e }) => e)
  const customizable = ordered.map((e) => e.item)
  // The customise dialog shows the sidebar as it is: favourites, each
  // section, then "Weitere".
  const groups: NavGroup[] = []
  const pinnedItems = pinned.map((path) => entries.find((e) => e.item.path === path)!.item)
  if (pinnedItems.length) {
    groups.push({ section: 'favourites', label: t('shell.sections.favourites'), items: pinnedItems })
  }
  for (const e of ordered) {
    if (pinned.includes(e.item.path)) continue
    const last = groups[groups.length - 1]
    if (last?.section === e.section) last.items.push(e.item)
    else
      groups.push({
        section: e.section,
        label: e.section === 'more' ? t('shell.nav.more') : t(`shell.sections.${e.section}`),
        items: [e.item],
      })
  }
  return { nav, more, customizable, groups, homes }
}

/** Prefs with `path` placed in `section` ("more" puts it under Weitere). */
function placeIn(prefs: NavPrefs, homes: NavHomes, path: string, section: string): NavPrefs {
  const hidden = prefs.hidden.filter((p) => p !== path)
  const sections = { ...(prefs.sections ?? {}) }
  if (section === 'more') {
    // Under Weitere; where it sat before stays known for the way back.
    return { ...prefs, hidden: [...hidden, path], sections }
  }
  if (homes[path] === section) delete sections[path]
  else sections[path] = section
  return { ...prefs, hidden, sections }
}

/** Prefs that keep `paths` in this order, in front of everything else. */
function withOrder(prefs: NavPrefs, paths: string[]): NavPrefs {
  const order = (prefs.order ?? []).filter((p) => !paths.includes(p))
  return { ...prefs, order: [...order, ...paths] }
}

/**
 * New prefs after moving `path` one step up (-1) or down (+1) in the
 * customise dialog. Within a group it swaps with its neighbour; past the
 * first or last entry it moves into the section above or below, "Weitere"
 * included. Favourites follow the pinned list and stay among themselves.
 */
export function moveNavEntry(
  prefs: NavPrefs,
  groups: NavGroup[],
  homes: NavHomes,
  path: string,
  step: -1 | 1,
): NavPrefs {
  const g = groups.findIndex((group) => group.items.some((item) => item.path === path))
  if (g < 0) return prefs
  const group = groups[g]
  const paths = group.items.map((item) => item.path)
  const i = paths.indexOf(path)
  const j = i + step
  if (j >= 0 && j < paths.length) {
    ;[paths[i], paths[j]] = [paths[j], paths[i]]
    if (group.section === 'favourites') {
      // Pinned entries the person can't see right now keep their place at the end.
      return { ...prefs, pinned: [...paths, ...prefs.pinned.filter((p) => !paths.includes(p))] }
    }
    return withOrder(prefs, paths)
  }
  const target = groups[g + step]
  if (!target || group.section === 'favourites' || target.section === 'favourites') return prefs
  const into = target.items.map((item) => item.path)
  // Moving down lands at the top of the next section, moving up at the bottom.
  const next = step > 0 ? [path, ...into] : [...into, path]
  return withOrder(placeIn(prefs, homes, path, target.section), next)
}

/**
 * New prefs with `path` moved under "Weitere", or out of it again: back to
 * the section it came from, or "Betrieb" for pages that start under Weitere.
 */
export function toggleNavMore(
  prefs: NavPrefs,
  homes: NavHomes,
  path: string,
  inMore: boolean,
): NavPrefs {
  if (!inMore) return placeIn(prefs, homes, path, 'more')
  const back = prefs.sections?.[path] ?? homes[path]
  return placeIn(prefs, homes, path, back && back !== 'more' ? back : 'operations')
}

/** Every path in the sidebar. */
export function navPaths(nav: NavSection[]): string[] {
  return nav.flatMap((section) => section.items.map((item) => item.path))
}

/**
 * The sidebar entry a page belongs to: the longest prefix of the path wins.
 * Built-in sub-pages map to their entry below; every other sidebar path
 * (plugins and modules added later) highlights its own pages.
 */
export function getParentPath(pathname: string, navPaths: string[] = []): string {
  const prefixes: [string, string][] = [
    ['/app/dashboard', '/app/dashboard'],
    ['/app/dashboard/global', '/app/dashboard'],
    ['/app/dashboard/me', '/app/dashboard'],
    ['/app/members', '/app/members'],
    ['/app/members/applications', '/app/members/applications'],
    ['/app/groups', '/app/groups'],
    ['/app/operations/events', '/app/operations/events'],
    ['/app/operations/polls', '/app/operations/polls'],
    ['/app/operations/posts', '/app/operations/posts'],
    ['/app/finance', '/app/finance'],
    ['/app/finance/transactions', '/app/finance'],
    ['/app/finance/invoices', '/app/finance'],
    ['/app/finance/categories', '/app/finance'],
    ['/app/mail', '/app/mail'],
    ['/app/operations/codes', '/app/operations/codes'],
    ['/app/operations/bindings', '/app/operations/bindings'],
    ['/app/inventory', '/app/inventory'],
    ['/app/settings', '/app/settings'],
    ['/app/audit-log', '/app/settings'],
    ['/app/system', '/app/settings'],
    ['/app/more', '/app/more'],
    ['/app/translations', '/app/translations'],
    ['/app/account', '/app/account/settings'],
    ['/app/account/settings', '/app/account/settings'],
  ]
  const known = new Set(prefixes.map(([prefix]) => prefix))
  for (const path of navPaths) {
    if (!known.has(path)) prefixes.push([path, path])
  }
  let best = '/app/dashboard'
  let bestLength = 0
  for (const [prefix, parent] of prefixes) {
    if (pathname === prefix || pathname.startsWith(prefix + '/')) {
      if (prefix.length > bestLength) {
        best = parent
        bestLength = prefix.length
      }
    }
  }
  return best
}

export function getBreadcrumb(
  pathname: string,
  t: (key: string) => string,
): string {
  const map: Record<string, string> = {
    '/app/dashboard': t('shell.breadcrumbs.dashboard'),
    '/app/dashboard/global': t('shell.breadcrumbs.dashboardGlobal'),
    '/app/dashboard/me': t('shell.breadcrumbs.dashboardMe'),
    '/app/members': t('shell.breadcrumbs.members'),
    '/app/members/applications': t('shell.breadcrumbs.applications'),
    '/app/members/tiers': t('shell.breadcrumbs.tiers'),
    '/app/members/functions': t('shell.breadcrumbs.functions'),
    '/app/groups': t('shell.breadcrumbs.groups'),
    '/app/operations/events': t('shell.breadcrumbs.events'),
    '/app/operations/events/attendance': t('shell.breadcrumbs.attendance'),
    '/app/operations/polls': t('shell.breadcrumbs.polls'),
    '/app/operations/posts': t('shell.breadcrumbs.posts'),
    '/app/finance': t('shell.breadcrumbs.finance'),
    '/app/finance/transactions': t('shell.breadcrumbs.transactions'),
    '/app/finance/invoices': t('shell.breadcrumbs.invoices'),
    '/app/finance/recurring': t('shell.breadcrumbs.recurring'),
    '/app/finance/fee-basis': t('shell.breadcrumbs.feeBasis'),
    '/app/finance/categories': t('shell.breadcrumbs.txCategories'),
    '/app/finance/external-parties': t('shell.breadcrumbs.externalParties'),
    '/app/finance/settings': t('shell.breadcrumbs.financeSettings'),
    '/app/mail': t('shell.breadcrumbs.mail'),
    '/app/operations/codes': t('shell.breadcrumbs.codes'),
    '/app/operations/bindings': t('shell.breadcrumbs.bindings'),
    '/app/settings': t('shell.breadcrumbs.settings'),
    '/app/account': t('shell.breadcrumbs.account'),
    '/app/account/settings': t('shell.breadcrumbs.accountSettings'),
    '/app/inventory': t('shell.breadcrumbs.inventory'),
    '/app/audit-log': t('shell.breadcrumbs.auditLog'),
    '/app/system': t('shell.breadcrumbs.system'),
    '/app/system/roles': t('shell.breadcrumbs.roles'),
    '/app/translations': t('shell.breadcrumbs.translations'),
  }
  if (map[pathname]) return map[pathname]
  if (/^\/app\/members\/[^/]+$/.test(pathname))
    return t('shell.breadcrumbs.memberDetail')
  if (/^\/app\/finance\/invoices\/[^/]+$/.test(pathname))
    return t('shell.breadcrumbs.invoiceDetail')
  if (/^\/app\/inventory\/[^/]+$/.test(pathname))
    return t('shell.breadcrumbs.inventoryItemDetail')
  // Sub-pages without their own entry (settings tabs, system tabs, …) show
  // the closest parent instead of nothing.
  const parent = Object.keys(map)
    .filter((p) => pathname.startsWith(p + '/'))
    .sort((a, b) => b.length - a.length)[0]
  return parent ? map[parent] : ''
}
