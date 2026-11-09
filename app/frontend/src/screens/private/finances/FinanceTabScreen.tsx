import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, SubTabs, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { InvoicesTab } from '@/screens/private/finances/InvoicesTab'
import { ExternalPartiesTab } from '@/screens/private/finances/ExternalPartiesTab'
import { FeeBasisTab } from '@/screens/private/finances/FeeBasisTab'
import { FinanceSettingsTab } from '@/screens/private/finances/FinanceSettingsTab'
import { BankSettingsCard } from '@/screens/private/settings/BankSettingsCard'
import { PluginBoundary, usePluginTabs } from '@/plugins'

/** One page of Finanzen, at /app/finance/<id>. */
type Part = { id: string; label: string; allowed: boolean; render: () => ReactNode }
/** A page tab; with more than one part it shows them as sub-tabs. */
type Group = { id: string; label: string; parts: Part[] }

/** Where the shipped plugins' tabs go, for versions that don't say. */
const PLUGIN_GROUPS: Record<string, string> = { bank: 'bookings', budgets: 'planning' }

const financePath = (id: string) => `/app/finance${id === 'overview' ? '' : '/' + id}`

/**
 * Finanzen in up to six page tabs: the overview, the invoices, the bookings,
 * planning (budgets, fee basis), the annual accounts and the set-up (billing
 * rules, the lists the bookings draw on, the bank account). Each part keeps
 * its own address, so old links still open the same page.
 *
 * Hubra itself brings the invoices, the fee basis and the set-up; the books
 * (overview, transactions, recurring bookings, categories, annual accounts)
 * are the Finances plugin's tabs, in the groups they name.
 */
export function FinanceTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const pluginTabs = usePluginTabs('finance')

  // The path may start with the club's slug: /<club>/app/finance/<tab>.
  const path = (location.pathname.split('/app/finance')[1] ?? '').replace('/', '')

  const known = new Set(['overview', 'invoices', 'bookings', 'planning', 'annual', 'setup'])
  const groupOf = (pt: (typeof pluginTabs)[number]) => pt.group ?? PLUGIN_GROUPS[pt.id]
  const pluginPart = (pt: (typeof pluginTabs)[number]): Part => ({
    id: pt.id,
    label: t(pt.label),
    allowed: true,
    render: () => (
      <PluginBoundary key={pt.id} plugin={pt.plugin} notice>
        <pt.component />
      </PluginBoundary>
    ),
  })
  const pluginParts = (group: string) =>
    pluginTabs.filter((pt) => groupOf(pt) === group).map(pluginPart)

  const groups: Group[] = [
    { id: 'overview', label: t('shell.nav.overview'), parts: pluginParts('overview') },
    {
      id: 'invoices',
      label: t('shell.nav.invoices'),
      parts: [
        {
          id: 'invoices',
          label: t('shell.nav.invoices'),
          allowed: hasPermission('finance.invoices.read'),
          render: () => <InvoicesTab />,
        },
        // Such as settling the Kasse plugin's tab, which makes invoices.
        ...pluginParts('invoices'),
      ],
    },
    {
      id: 'bookings',
      label: t('finance.groups.bookings', 'Buchungen'),
      parts: pluginParts('bookings'),
    },
    {
      id: 'planning',
      label: t('finance.groups.planning', 'Budget & Beiträge'),
      parts: pluginParts('planning'),
    },
    // Plugin tabs that name no group (or one this screen doesn't have).
    ...pluginTabs
      .filter((pt) => !known.has(groupOf(pt) ?? ''))
      .map((pt) => ({ id: pt.id, label: t(pt.label), parts: [pluginPart(pt)] })),
    // The year-end report for the general meeting, with its chart of accounts.
    {
      id: 'annual',
      label: t('shell.nav.annualAccounts', 'Jahresrechnung'),
      parts: pluginParts('annual'),
    },
    {
      id: 'setup',
      label: t('finance.settings.tab', 'Einstellungen'),
      parts: [
        {
          id: 'settings',
          label: t('finance.groups.billing', 'Abrechnung'),
          // The billing rules are the finance module's settings.
          allowed: hasPermission('modules.modules.write'),
          render: () => <FinanceSettingsTab />,
        },
        // How the yearly expenses the percentage tiers share come together:
        // a rule set once, so it sits with the other finance settings.
        {
          id: 'fee-basis',
          label: t('shell.nav.feeBasis', 'Beitragsgrundlage'),
          allowed: hasPermission('finance.overview.read'),
          render: () => <FeeBasisTab />,
        },
        {
          id: 'external-parties',
          label: t('shell.nav.externalParties', 'Externe Parteien'),
          allowed: hasPermission('finance.external_parties.read'),
          render: () => <ExternalPartiesTab />,
        },
        ...pluginParts('setup'),
        {
          id: 'bank-account',
          label: t('settings.tabs.bank', 'Bank & QR-Rechnung'),
          allowed: hasPermission('settings.settings.read'),
          render: () => <BankSettingsCard />,
        },
      ],
    },
  ]
    .map((g) => ({ ...g, parts: g.parts.filter((p) => p.allowed) }))
    .filter((g) => g.parts.length > 0)

  // /app/finance opens the overview, or the first page there is without it.
  const active = path === '' ? (groups[0]?.parts[0]?.id ?? 'invoices') : path
  const group = groups.find((g) => g.parts.some((p) => p.id === active))
  const part = group?.parts.find((p) => p.id === active)

  return (
    <div>
      <PageHead title={t('shell.nav.finance', 'Finanzen')} />
      <Tabs
        // A page tab with a single part is named after it, such as
        // "Budgets" when only the budgets plugin fills "Budget & Beiträge".
        tabs={groups.map((g) => ({
          id: g.id,
          label: g.parts.length === 1 && g.id !== 'setup' ? g.parts[0].label : g.label,
        }))}
        activeTab={group?.id ?? ''}
        onTabChange={(id) => {
          const first = groups.find((g) => g.id === id)?.parts[0]
          if (first) navigate(financePath(first.id))
        }}
        label={t('shell.nav.finance', 'Finanzen')}
        mb={group && group.parts.length > 1 ? 12 : 24}
      />
      {group && group.parts.length > 1 && (
        <SubTabs
          tabs={group.parts.map((p) => ({ id: p.id, label: p.label }))}
          activeTab={active}
          onTabChange={(id) => navigate(financePath(id))}
          label={group.label}
        />
      )}
      {part?.render()}
    </div>
  )
}
