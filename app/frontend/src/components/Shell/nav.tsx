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

export function contrastColor(hex: string): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return lum > 140 ? '#1a1625' : '#ffffff'
}

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

/** An icon a plugin brought along, or a box. */
function navIcon(name: string): ReactNode {
  const Icon = pluginIcon(name)
  return Icon ? <Icon size={24} /> : <IconBox size={24} />
}

const SECTION_ORDER = ['favourites', 'workspace', 'activities', 'operations', 'system', 'me']

/** Where the "Weitere" entry lists the pages that have no sidebar row. */
export const MORE_PATH = '/app/more'

/** The person's own sidebar: entries pinned to the top and entries hidden. */
export type NavPrefs = { pinned: string[]; hidden: string[] }
const NO_PREFS: NavPrefs = { pinned: [], hidden: [] }

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
 * as "Favoriten", and everything hidden or secondary on the "Weitere" page.
 * `more` lists those pages; the sidebar shows one "Weitere" entry for them.
 */
export function buildNav(
  c: NavCounts,
  t: (key: string, params?: Record<string, unknown>) => string,
  modules: ModuleInfo[],
  hasPerm: (key: string) => boolean = () => true,
  prefs: NavPrefs = NO_PREFS,
): { nav: NavSection[]; more: NavItem[]; customizable: NavItem[] } {
  const entries = navEntries(c, t, modules).filter(
    ({ item }) => !item.permKeys || item.permKeys.some(hasPerm),
  )
  const hidden = new Set(prefs.hidden)
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
    if (section === 'more' || (section !== 'me' && hidden.has(item.path))) more.push(item)
    else add(section, item)
  }
  if (more.length > 0) {
    add('operations', {
      path: MORE_PATH,
      label: t('shell.nav.more'),
      icon: <IconDots size={24} />,
    })
  }
  const nav = [...sections.entries()]
    .sort(
      ([a], [b]) =>
        (SECTION_ORDER.indexOf(a) + 1 || 99) - (SECTION_ORDER.indexOf(b) + 1 || 99),
    )
    .map(([section, list]) => ({
      label: t(`shell.sections.${section}`),
      items: list,
    }))
  // In sidebar order, with the "Weitere" pages last.
  const rank = (section: string) => SECTION_ORDER.indexOf(section) + 1 || 99
  const customizable = entries
    .filter((e) => e.section !== 'me')
    .sort((a, b) => rank(a.section) - rank(b.section))
    .map((e) => e.item)
  return { nav, more, customizable }
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
    '/app/operations/polls': t('shell.breadcrumbs.polls'),
    '/app/operations/posts': t('shell.breadcrumbs.posts'),
    '/app/finance': t('shell.breadcrumbs.finance'),
    '/app/finance/transactions': t('shell.breadcrumbs.transactions'),
    '/app/finance/invoices': t('shell.breadcrumbs.invoices'),
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
