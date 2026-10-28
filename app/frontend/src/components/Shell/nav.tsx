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
  IconDevicesCog,
  IconLink,
} from '@tabler/icons-react'
import type { ReactNode } from 'react'

export type NavItem = {
  path: string
  label: string
  icon: ReactNode
  count?: number
  permKeys?: string[]
  featureKey?: string
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
  return lum > 140 ? '#181818' : '#ffffff'
}

export function buildNav(
  c: NavCounts,
  t: (key: string, params?: Record<string, unknown>) => string,
): NavSection[] {
  return [
    {
      label: t('shell.sections.workspace'),
      items: [
        {
          path: '/app/dashboard',
          label: t('shell.nav.dashboard'),
          icon: <IconLayoutDashboard size={24} />,
        },
        {
          path: '/app/members',
          label: t('shell.nav.members'),
          icon: <IconUsers size={24} />,
          count: c.members || undefined,
          permKeys: [
            'members.members.read',
            'functions.functions.read',
            'applications.applications.read',
            'tiers.tiers.read',
          ],
        },
        {
          path: '/app/groups',
          label: t('shell.nav.groups'),
          icon: <IconBox size={24} />,
          count: c.groups || undefined,
          permKeys: ['groups.groups.read'],
        },
        {
          path: '/app/inventory',
          label: t('shell.nav.inventory'),
          icon: <IconPackage size={24} />,
          permKeys: ['inventory.items.read'],
        },
        {
          path: '/app/operations/events',
          label: t('shell.nav.management'),
          icon: <IconLayoutList size={24} />,
        },
      ],
    },
    {
      label: t('shell.sections.operations'),
      items: [
        {
          path: '/app/finance',
          label: t('shell.nav.finance'),
          icon: <IconWallet size={24} />,
          permKeys: [
            'finance.overview.read',
            'finance.transactions.read',
            'finance.invoices.read',
            'finance.transaction_categories.read',
          ],
        },
        {
          path: '/app/mail',
          label: t('shell.nav.mail'),
          icon: <IconMail size={24} />,
          featureKey: 'mail',
          permKeys: [
            'mail.mailboxes.read',
            'mail.aliases.read',
            'mail.system.read',
            'mail.member_mail.read',
            'mail.wildduck.read',
          ],
        },
        {
          path: '/app/operations/codes',
          label: t('shell.nav.codes'),
          icon: <IconKey size={24} />,
          permKeys: ['codes.codes.read'],
        },
        {
          path: '/app/operations/bindings',
          label: t('shell.nav.bindings'),
          icon: <IconLink size={24} />,
          permKeys: ['bindings.bindings.read'],
        },
      ],
    },
    {
      label: t('shell.sections.system'),
      items: [
        {
          path: '/app/settings',
          label: t('shell.nav.settings'),
          icon: <IconSettings size={24} />,
          permKeys: ['settings.settings.read'],
        },
        {
          path: '/app/audit-log',
          label: t('shell.nav.auditLog'),
          icon: <IconShield size={24} />,
          permKeys: ['audit.audit.read'],
        },
        {
          path: '/app/system',
          label: t('shell.nav.permissions'),
          icon: <IconDevicesCog size={24} />,
          permKeys: [
            'roles.roles.create',
            'roles.roles.update',
            'roles.roles.set_permissions',
            'roles.roles.delete',
          ],
        },
        {
          path: '/app/translations',
          label: t('shell.nav.translations'),
          icon: <IconGlobe size={24} />,
          permKeys: ['i18n.i18n.write'],
        },
      ],
    },
    {
      label: t('shell.sections.me'),
      items: [
        {
          path: '/app/account/settings',
          label: t('shell.nav.accountSettings'),
          icon: <IconUser size={24} />,
        },
      ],
    },
  ]
}

export function filterNav(
  nav: NavSection[],
  hasPerm: (key: string) => boolean,
  features: Record<string, boolean> = {},
): NavSection[] {
  return nav
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          (!item.featureKey || features[item.featureKey] === true) &&
          (!item.permKeys || item.permKeys.some(hasPerm)),
      ),
    }))
    .filter((section) => section.items.length > 0)
}

export function getParentPath(pathname: string): string {
  const prefixes: [string, string][] = [
    ['/app/dashboard', '/app/dashboard'],
    ['/app/dashboard/global', '/app/dashboard'],
    ['/app/members', '/app/members'],
    ['/app/members/functions', '/app/members'],
    ['/app/members/applications', '/app/members'],
    ['/app/members/tiers', '/app/members'],
    ['/app/groups', '/app/groups'],
    ['/app/operations/events', '/app/operations/events'],
    ['/app/operations/polls', '/app/operations/events'],
    ['/app/operations/posts', '/app/operations/events'],
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
    ['/app/system/health', '/app/system'],
    ['/app/system/backups', '/app/system'],
    ['/app/translations', '/app/translations'],
    ['/app/account', '/app/account/settings'],
    ['/app/account/settings', '/app/account/settings'],
  ]
  let best = '/app/dashboard'
  for (const [prefix, parent] of prefixes) {
    if (pathname === prefix || pathname.startsWith(prefix + '/')) {
      if (prefix.length > best.length || best === '/app/dashboard') {
        best = parent
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
    '/app/mail': t('shell.breadcrumbs.mail'),
    '/app/operations/codes': t('shell.breadcrumbs.codes'),
    '/app/operations/bindings': t('shell.breadcrumbs.bindings'),
    '/app/settings': t('shell.breadcrumbs.settings'),
    '/app/account': t('shell.breadcrumbs.account'),
    '/app/account/settings': t('shell.breadcrumbs.accountSettings'),
    '/app/inventory': t('shell.breadcrumbs.inventory'),
    '/app/audit-log': t('shell.breadcrumbs.auditLog'),
    '/app/system': t('shell.breadcrumbs.system'),
    '/app/translations': t('shell.breadcrumbs.translations'),
  }
  if (map[pathname]) return map[pathname]
  if (/^\/app\/members\/[^/]+$/.test(pathname))
    return `${t('shell.breadcrumbs.members')} > ${t(
      'shell.breadcrumbs.memberDetail',
    )}`
  if (/^\/app\/finance\/invoices\/[^/]+$/.test(pathname))
    return `${t('shell.breadcrumbs.finance')} > ${t(
      'shell.breadcrumbs.invoiceDetail',
    )}`
  if (/^\/app\/inventory\/[^/]+$/.test(pathname))
    return `${t('shell.breadcrumbs.inventory')} > ${t(
      'shell.breadcrumbs.inventoryItemDetail',
    )}`
  return ''
}
