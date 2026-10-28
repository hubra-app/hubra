import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { FinanceOverviewTab } from '@/screens/private/finances/FinanceOverviewTab'
import { TransactionsTab } from '@/screens/private/finances/TransactionsTab'
import { InvoicesTab } from '@/screens/private/finances/InvoicesTab'
import { TransactionCategoriesTab } from '@/screens/private/finances/TransactionCategoriesTab'
import { ExternalPartiesTab } from '@/screens/private/finances/ExternalPartiesTab'
import { usePluginTabs } from '@/plugins'

export function FinanceTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const pluginTabs = usePluginTabs('finance')

  // The path may start with the club's slug: /<club>/app/finance/<tab>.
  const path = (location.pathname.split('/app/finance')[1] ?? '').replace('/', '')
  const tab = path === '' ? 'overview' : path

  const tabs = [
    { id: 'overview', label: t('shell.nav.overview') },
    { id: 'transactions', label: t('shell.nav.incomeExpenses') },
    { id: 'invoices', label: t('shell.nav.invoices') },
    { id: 'categories', label: t('shell.nav.txCategories') },
    {
      id: 'external-parties',
      label: t('shell.nav.externalParties', 'Extern'),
    },
  ].filter(
    (tb) =>
      tb.id === 'overview' ||
      (tb.id === 'transactions' &&
        hasPermission('finance.transactions.read')) ||
      (tb.id === 'invoices' && hasPermission('finance.invoices.read')) ||
      (tb.id === 'categories' &&
        hasPermission('finance.transaction_categories.read')) ||
      (tb.id === 'external-parties' &&
        hasPermission('finance.external_parties.read')),
  )
  tabs.push(...pluginTabs.map((pt) => ({ id: pt.id, label: t(pt.label) })))
  const PluginTab = pluginTabs.find((pt) => pt.id === tab)?.component

  return (
    <div>
      <PageHead title={t('shell.nav.finance', 'Finanzen')} />
      <Tabs
        tabs={tabs}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(`/app/finance${id === 'overview' ? '' : '/' + id}`)
        }
      />
      {tab === 'overview' && <FinanceOverviewTab />}
      {tab === 'transactions' && <TransactionsTab />}
      {tab === 'invoices' && <InvoicesTab />}
      {tab === 'categories' && <TransactionCategoriesTab />}
      {tab === 'external-parties' && <ExternalPartiesTab />}
      {PluginTab && <PluginTab />}
    </div>
  )
}
