import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, SubTabs, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { FinanceOverviewTab } from '@/screens/private/finances/FinanceOverviewTab'
import { TransactionsTab } from '@/screens/private/finances/TransactionsTab'
import { InvoicesTab } from '@/screens/private/finances/InvoicesTab'
import { TransactionCategoriesTab } from '@/screens/private/finances/TransactionCategoriesTab'
import { ExternalPartiesTab } from '@/screens/private/finances/ExternalPartiesTab'
import { RecurringTab } from '@/screens/private/finances/RecurringTab'
import { FeeBasisTab } from '@/screens/private/finances/FeeBasisTab'
import { FinanceSettingsTab } from '@/screens/private/finances/FinanceSettingsTab'
import { AnnualAccountsTab } from '@/screens/private/finances/AnnualAccountsTab'
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
 * Finanzen in five page tabs: the overview, the invoices, the bookings,
 * planning (budgets, fee basis) and the set-up (billing rules, the lists the
 * bookings draw on, the bank account), plus the annual accounts for those who
 * may read them. Each part keeps its own address, so old links still open
 * the same page.
 */
export function FinanceTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const pluginTabs = usePluginTabs('finance')

  // The path may start with the club's slug: /<club>/app/finance/<tab>.
  const path = (location.pathname.split('/app/finance')[1] ?? '').replace('/', '')
  const active = path === '' ? 'overview' : path

  const known = new Set(['bookings', 'planning', 'setup'])
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
    {
      id: 'overview',
      label: t('shell.nav.overview'),
      parts: [
        {
          id: 'overview',
          label: t('shell.nav.overview'),
          allowed: true,
          render: () => <FinanceOverviewTab />,
        },
      ],
    },
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
      ],
    },
    {
      id: 'bookings',
      label: t('finance.groups.bookings', 'Buchungen'),
      parts: [
        {
          id: 'transactions',
          label: t('shell.nav.incomeExpenses'),
          allowed: hasPermission('finance.transactions.read'),
          render: () => <TransactionsTab />,
        },
        {
          id: 'recurring',
          label: t('shell.nav.recurring', 'Wiederkehrend'),
          allowed: hasPermission('finance.transactions.read'),
          render: () => <RecurringTab />,
        },
        ...pluginParts('bookings'),
      ],
    },
    {
      id: 'planning',
      label: t('finance.groups.planning', 'Budget & Beiträge'),
      parts: [
        ...pluginParts('planning'),
        {
          id: 'fee-basis',
          label: t('shell.nav.feeBasis', 'Beitragsgrundlage'),
          allowed: hasPermission('finance.overview.read'),
          render: () => <FeeBasisTab />,
        },
      ],
    },
    // Plugin tabs that name no group (or one this screen doesn't have).
    ...pluginTabs
      .filter((pt) => !known.has(groupOf(pt) ?? ''))
      .map((pt) => ({ id: pt.id, label: t(pt.label), parts: [pluginPart(pt)] })),
    // The year-end report for the general meeting, with its chart of accounts.
    {
      id: 'annual',
      label: t('shell.nav.annualAccounts', 'Jahresrechnung'),
      parts: [
        {
          id: 'annual',
          label: t('shell.nav.annualAccounts', 'Jahresrechnung'),
          allowed: hasPermission('finance.accounts.read'),
          render: () => <AnnualAccountsTab />,
        },
      ],
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
        {
          id: 'categories',
          label: t('shell.nav.txCategories'),
          allowed: hasPermission('finance.transaction_categories.read'),
          render: () => <TransactionCategoriesTab />,
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

  const group = groups.find((g) => g.parts.some((p) => p.id === active))
  const part = group?.parts.find((p) => p.id === active)

  return (
    <div>
      <PageHead title={t('shell.nav.finance', 'Finanzen')} />
      <Tabs
        // A page tab with a single part is named after it, such as
        // "Beitragsgrundlage" when no budgets plugin is on.
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
