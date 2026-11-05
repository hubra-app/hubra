import { useState } from 'react'
import { Button, Group, Paper, Stack, Text } from '@mantine/core'
import { IconDeviceMobileDown } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { promptInstall, useInstallState } from '@/pwa'

/** Add Hubra to the home screen or dock as an app (PWA). */
export function InstallAppCard() {
  const { t } = useT()
  const state = useInstallState()
  const [busy, setBusy] = useState(false)
  // Already installed, or a browser that cannot install apps (Firefox desktop).
  if (state === 'installed' || state === 'unavailable') return null

  const install = async () => {
    setBusy(true)
    try {
      await promptInstall()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder data-testid="install-app-card">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconDeviceMobileDown size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.installApp.title', 'Hubra als App')}
        </Text>
      </Group>
      <Stack p="md" gap="sm" align="flex-start">
        <Text fz="sm" c="dimmed">
          {state === 'ios'
            ? t(
                'account.installApp.ios',
                'Tippe in Safari auf Teilen und dann auf «Zum Home-Bildschirm». Hubra öffnet sich dann wie eine App, mit deinem Verein und ohne Browserleiste.',
              )
            : t(
                'account.installApp.hint',
                'Leg Hubra auf den Home-Bildschirm oder ins Dock. Die App öffnet deinen Verein direkt, ohne Browserleiste.',
              )}
        </Text>
        {state === 'prompt' && (
          <Button size="sm" onClick={install} loading={busy}>
            {t('account.installApp.button', 'App installieren')}
          </Button>
        )}
      </Stack>
    </Paper>
  )
}
