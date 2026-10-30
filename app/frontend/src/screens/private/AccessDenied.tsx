import { useT } from '@/locales/i18n'
import { Button } from '@mantine/core'
import { IconShieldCheckFilled } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'

export function AccessDeniedScreen() {
  const { t } = useT()
  const navigate = useNavigate()

  return (
    <div style={{ padding: 48, textAlign: 'center' }}>
      <IconShieldCheckFilled
        size={40}
        style={{ color: '#ff4d3d', marginBottom: 16 }}
      />
      <div
        style={{
          fontSize: 'var(--mantine-font-size-lg)',
          fontWeight: 700,
          marginBottom: 8,
        }}
      >
        {t('shell.accessDenied', 'Kein Zugriff')}
      </div>
      <div style={{ color: 'var(--hb-text-2)', marginBottom: 24 }}>
        {t(
          'shell.noPermission',
          'Du hast keine Berechtigung für diese Seite.',
        )}
      </div>
      <Button variant="filled" onClick={() => navigate('/app/dashboard')}>
        {t('shell.goToDashboard', 'Zum Dashboard')}
      </Button>
    </div>
  )
}
