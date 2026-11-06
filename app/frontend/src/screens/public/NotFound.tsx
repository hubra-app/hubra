import { Button, Group, Stack, Text, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { IconArrowLeft, IconBug } from '@tabler/icons-react'
import { hasTokens } from '@hubra/api-client'
import { reportProblemUrl } from '@/constants'

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
        <Group mt="md" justify="center" gap="sm">
          <Button leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(target)}>
            {t('common.goHome', 'Zur Startseite')}
          </Button>
          {/* A broken link is a problem worth hearing about: the address goes along. */}
          <Button
            component="a"
            href={reportProblemUrl(window.location.href)}
            variant="default"
            leftSection={<IconBug size={16} />}
            data-testid="notfound-report"
          >
            {t('support.menu.bug', 'Problem melden')}
          </Button>
        </Group>
      </Stack>
    </div>
  )
}
