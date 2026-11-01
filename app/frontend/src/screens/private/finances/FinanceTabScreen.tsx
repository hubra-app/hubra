import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { FinanceOverviewTab } from '@/screens/private/finances/FinanceOverviewTab'
import { TransactionsTab } from '@/screens/private/finances/TransactionsTab'
import { InvoicesTab } from '@/screens/private/finances/InvoicesTab'
import { TransactionCategoriesTab } from '@/screens/private/finances/TransactionCategoriesTab'
import { ExternalPartiesTab } from '@/screens/private/finances/ExternalPartiesTab'
import { RecurringTab } from '@/screens/private/finances/RecurringTab'
import { FeeBasisTab } from '@/screens/private/finances/FeeBasisTab'
import { FinanceSettingsTab } from '@/screens/private/finances/FinanceSettingsTab'
import { PluginBoundary, usePluginTabs } from '@/plugins'

export function FinanceTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const pluginTabs = usePluginTabs('finance')

  // The path may start with the club's slug: /<club>/app/finance/<tab>.
  const path = (location.pathname.split('/app/finance')[1] ?? '').replace('/', '')
  const tab = path === '' ? 'overview' : path

  // Daily work first (invoices, bookings and what plugins add, such as
  // budgets or the bank import), then the lists they draw on, then the
  // rules for billing.
  const can: Record<string, boolean> = {
    invoices: hasPermission('finance.invoices.read'),
    transactions: hasPermission('finance.transactions.read'),
    recurring: hasPermission('finance.transactions.read'),
    categories: hasPermission('finance.transaction_categories.read'),
    'external-parties': hasPermission('finance.external_parties.read'),
    'fee-basis': hasPermission('finance.overview.read'),
    // The billing rules are the finance module's settings.
    settings: hasPermission('modules.modules.write'),
  }
  const tabs = [
    { id: 'overview', label: t('shell.nav.overview') },
    { id: 'invoices', label: t('shell.nav.invoices') },
    { id: 'transactions', label: t('shell.nav.incomeExpenses') },
    { id: 'recurring', label: t('shell.nav.recurring', 'Wiederkehrend') },
    ...pluginTabs.map((pt) => ({ id: pt.id, label: t(pt.label) })),
    { id: 'categories', label: t('shell.nav.txCategories') },
    {
      id: 'external-parties',
      label: t('shell.nav.externalParties', 'Extern'),
    },
    { id: 'fee-basis', label: t('shell.nav.feeBasis', 'Beitragsgrundlage') },
    { id: 'settings', label: t('finance.settings.tab', 'Einstellungen') },
  ].filter((tb) => can[tb.id] ?? true)
  const pluginTab = pluginTabs.find((pt) => pt.id === tab)

  return (
    <div>
      <PageHead title={t('shell.nav.finance', 'Finanzen')} />
      <Tabs
        tabs={tabs}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/finance${id === 'overview' ? '' : '/' + id}`)}
      />
      {tab === 'overview' && <FinanceOverviewTab />}
      {tab === 'transactions' && <TransactionsTab />}
      {tab === 'recurring' && can.recurring && <RecurringTab />}
      {tab === 'invoices' && <InvoicesTab />}
      {tab === 'categories' && <TransactionCategoriesTab />}
      {tab === 'external-parties' && <ExternalPartiesTab />}
      {tab === 'fee-basis' && can['fee-basis'] && <FeeBasisTab />}
      {tab === 'settings' && can.settings && <FinanceSettingsTab />}
      {pluginTab && (
        <PluginBoundary key={pluginTab.id} plugin={pluginTab.plugin} notice>
          <pluginTab.component />
        </PluginBoundary>
      )}
    </div>
  )
}
