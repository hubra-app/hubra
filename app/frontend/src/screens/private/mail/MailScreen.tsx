import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { AddressesTab } from '@/screens/private/mail/AddressesTab'
import { SystemMailTab } from '@/screens/private/mail/SystemMailTab'
import { WildDuckLiveTab } from '@/screens/private/mail/WildDuckLiveTab'

const OwnedAddressesTab = () => <AddressesTab scope="owned" />
const AllAddressesTab = () => <AddressesTab scope="all" />

const TABS = [
  {
    key: 'addresses',
    labelKey: 'mail.admin.tabAddresses',
    Component: OwnedAddressesTab,
  },
  { key: 'system', labelKey: 'mail.admin.tabSystem', Component: SystemMailTab },
  {
    key: 'all',
    labelKey: 'mail.admin.tabAll',
    Component: AllAddressesTab,
  },
  {
    key: 'wildduck',
    labelKey: 'mail.admin.tabWildDuck',
    Component: WildDuckLiveTab,
  },
] as const

export function MailScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const activeTab = location.pathname.replace('/app/mail', '').replace('/', '') || 'addresses'

  const ActiveComponent = TABS.find((tab) => tab.key === activeTab)?.Component ?? OwnedAddressesTab

  return (
    <div>
      <PageHead title={t('shell.breadcrumbs.mail', 'Mail › Verwaltung')} />
      <Tabs
        tabs={TABS.map((tab) => ({ id: tab.key, label: t(tab.labelKey) }))}
        activeTab={activeTab}
        onTabChange={(id) => navigate(`/app/mail${id === 'addresses' ? '' : '/' + id}`)}
      />
      <ActiveComponent />
    </div>
  )
}
