import { useT } from '@/locales/i18n'
import { PageHead } from '@/components/ui'
import { RolesTab } from '@/screens/private/system/RolesTab'

// System health and the API permission table are the platform's: they
// live in manage under Platform → Diagnostics.
export function SystemScreen() {
  const { t } = useT()
  return (
    <div style={{ padding: '0 0 2rem' }}>
      <PageHead title={t('system.roles', 'Rollen')} />
      <RolesTab />
    </div>
  )
}
