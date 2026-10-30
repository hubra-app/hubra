import { Button, Stack, Text, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { IconArrowLeft } from '@tabler/icons-react'
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
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
        background: 'var(--hb-surface-2)',
      }}
    >
      <Stack align="center" gap="sm" maw={420} ta="center">
        <div className="logo-mark" style={{ width: 48, height: 48, marginBottom: 8 }} />
        <Text className="num" fz="sm" fw={600} c="acc.7">
          404
        </Text>
        <Title order={1}>{t('common.pageNotFound', 'Seite nicht gefunden')}</Title>
        <Text c="dimmed">
          {t(
            'common.pageNotFoundDesc',
            'Diese Seite gibt es nicht oder sie wurde verschoben.',
          )}
        </Text>
        <Button mt="md" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(target)}>
          {t('common.goHome', 'Zur Startseite')}
        </Button>
      </Stack>
    </div>
  )
}
