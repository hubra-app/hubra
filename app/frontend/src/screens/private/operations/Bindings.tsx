import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { BindingsTab } from './bindings/BindingsTab'
import { KeysTab } from './bindings/KeysTab'

type Tab = 'keys' | 'bindings'

export function BindingsScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const tab: Tab = location.pathname.includes('/list') ? 'bindings' : 'keys'
  return (
    <div>
      <PageHead title={t('bindings.title', 'Verknüpfungen')} actions={null} />
      <Tabs
        tabs={[
          { id: 'keys', label: t('bindings.internalKeys', 'Interne Schlüssel') },
          { id: 'bindings', label: t('bindings.tab', 'Verknüpfungen') },
        ]}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(
            `/app/operations/bindings${id === 'bindings' ? '/list' : ''}`,
          )
        }
      />
      {tab === 'keys' && <KeysTab />}
      {tab === 'bindings' && <BindingsTab />}
    </div>
  )
}

