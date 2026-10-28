import { Button } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { IconHome } from '@tabler/icons-react'
import { hasTokens } from '@hubra/api-client'

export function NotFoundScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const target = hasTokens() ? '/app/dashboard' : '/login'

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 32,
      }}
      className="graph-bg"
    >
      <div style={{ fontSize: 64, fontWeight: 800, color: '#181818' }}>404</div>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-lg)',
          fontWeight: 600,
          color: '#3a4048',
        }}
      >
        {t('common.pageNotFound', 'Page not found')}
      </div>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-sm)',
          color: '#6b7480',
          textAlign: 'center',
          maxWidth: 360,
        }}
      >
        {t(
          'common.pageNotFoundDesc',
          'The page you are looking for does not exist or has been moved.',
        )}
      </div>
      <Button
        variant="filled"
        style={{ marginTop: 8 }}
        onClick={() => navigate(target)}
      >
        <IconHome size={16} />
        {t('common.goHome', 'Go home')}
      </Button>
    </div>
  )
}
