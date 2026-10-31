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
  /** Sub-pages shown indented below this entry. */
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

const SECTION_ORDER = ['workspace', 'activities', 'operations', 'system', 'me']

/** Sidebar entries come from the modules that are on for the active club. */
export function buildNav(
  c: NavCounts,
  t: (key: string, params?: Record<string, unknown>) => string,
  modules: ModuleInfo[],
): NavSection[] {
  const counts: Record<string, number> = {
    '/app/members': c.members,
    '/app/members/applications': c.applications,
    '/app/groups': c.groups,
  }
  const items = modules
    .filter((m) => m.enabled)
    .flatMap((m) => m.nav)
    .sort((a, b) => a.order - b.order)
  const sections = new Map<string, NavItem[]>()
  const seenGroups = new Set<string>()
  const byPath = new Map<string, NavItem>()
  const children: { parent: string; item: NavItem }[] = []
  for (const item of items) {
    // Modules shown as tabs of one screen share a single entry.
    if (item.group) {
      if (seenGroups.has(item.group)) continue
      seenGroups.add(item.group)
    }
    const entry: NavItem = {
      path: item.path,
      label: t(item.labelKey),
      icon: NAV_ICONS[item.icon] ?? navIcon(item.icon),
      count: counts[item.path] || undefined,
      countTitle:
        item.path === '/app/members'
          ? t('shell.nav.activeMembersCount', { count: counts[item.path] })
          : undefined,
      permKeys: item.perms.length ? item.perms : undefined,
    }
    if (item.parent) {
      children.push({ parent: item.parent, item: entry })
      continue
    }
    byPath.set(item.path, entry)
    const list = sections.get(item.section) ?? []
    list.push(entry)
    sections.set(item.section, list)
  }
  for (const { parent, item } of children) {
    const host = byPath.get(parent)
    if (host) host.children = [...(host.children ?? []), item]
  }
  return [...sections.entries()]
    .sort(
      ([a], [b]) =>
        (SECTION_ORDER.indexOf(a) + 1 || 99) - (SECTION_ORDER.indexOf(b) + 1 || 99),
    )
    .map(([section, list]) => ({
      label: t(`shell.sections.${section}`),
      items: list,
    }))
}

/** Every path in the sidebar, sub-pages included. */
export function navPaths(nav: NavSection[]): string[] {
  return nav.flatMap((section) =>
    section.items.flatMap((item) => [item.path, ...(item.children ?? []).map((c) => c.path)]),
  )
}

export function filterNav(
  nav: NavSection[],
  hasPerm: (key: string) => boolean,
): NavSection[] {
  return nav
    .map((section) => ({
      ...section,
      items: section.items
        .filter((item) => !item.permKeys || item.permKeys.some(hasPerm))
        .map((item) => ({
          ...item,
          children: item.children?.filter(
            (child) => !child.permKeys || child.permKeys.some(hasPerm),
          ),
        })),
    }))
    .filter((section) => section.items.length > 0)
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
    ['/app/members/functions', '/app/members/functions'],
    ['/app/members/applications', '/app/members/applications'],
    ['/app/members/tiers', '/app/members/tiers'],
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
    ['/app/audit-log', '/app/audit-log'],
    ['/app/system', '/app/system'],
    ['/app/system/roles', '/app/system'],
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
