import { useEffect, useState } from 'react'
import { Group, Paper, Stack, Switch, Text } from '@mantine/core'
import { IconDeviceMobileMessage } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { disablePush, enablePush, pushState, type PushState } from '@/api/push'

/** Browser notifications on this device: the bell's notifications as pushes. */
export function PushCard() {
  const { t } = useT()
  const { notify } = useToast()
  const [state, setState] = useState<PushState | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let live = true
    pushState()
      .then((s) => live && setState(s))
      .catch(() => live && setState('off'))
    return () => {
      live = false
    }
  }, [])
  if (state === null || state === 'unsupported') return null

  const toggle = async (on: boolean) => {
    setBusy(true)
    try {
      setState(await (on ? enablePush() : disablePush()))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  const hint =
    state === 'needs-install'
      ? t(
          'account.push.needsInstall',
          'Auf iPhone und iPad zuerst Hubra zum Home-Bildschirm hinzufügen (Teilen › Zum Home-Bildschirm), dann hier einschalten.',
        )
      : state === 'denied'
        ? t(
            'account.push.denied',
            'Mitteilungen sind für diese Seite im Browser blockiert. Erlaube sie in den Website-Einstellungen des Browsers.',
          )
        : t(
            'account.push.hint',
            'Alles, was in der Glocke erscheint (Erinnerungen, neue Anlässe, Umfragen), auch als Mitteilung auf diesem Gerät, für alle deine Vereine.',
          )

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconDeviceMobileMessage size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.push.title', 'Mitteilungen auf diesem Gerät')}
        </Text>
      </Group>
      <Stack p="md" gap="sm">
        <Text fz="sm" c="dimmed">
          {hint}
        </Text>
        <Switch
          label={t('account.push.switch', 'Browser-Mitteilungen')}
          checked={state === 'on'}
          disabled={busy || state === 'needs-install' || state === 'denied'}
          onChange={(e) => toggle(e.currentTarget.checked)}
        />
      </Stack>
    </Paper>
  )
}
