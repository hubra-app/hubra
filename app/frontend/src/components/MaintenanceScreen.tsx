import { useEffect, useState } from 'react'
import { Anchor, Center, Overlay, Paper, Stack, Text } from '@mantine/core'
import { IconTool } from '@tabler/icons-react'
import { getMaintenance, setMaintenanceHandler, type MaintenanceState } from '@hubra/api-client'
import { useT } from '@/locales/i18n'
import { useInstance } from '@/context/InstanceContext'
import { URL_CLUB } from '@/clubBase'

const POLL_MS = 30_000

/** While the platform is in maintenance the club API answers 503; this page
 * covers the app, says when it should be back and reloads once it is. */
export function MaintenanceScreen() {
  const { t, i18n } = useT()
  const { ssoUrl } = useInstance()
  const [state, setState] = useState<MaintenanceState | null>(null)

  useEffect(() => {
    setMaintenanceHandler((s) => setState(s))
    const ctrl = new AbortController()
    getMaintenance(ctrl.signal)
      .then((s) => s.active && setState(s))
      .catch(() => {})
    return () => {
      setMaintenanceHandler(null)
      ctrl.abort()
    }
  }, [])

  useEffect(() => {
    if (!state?.active) return
    const timer = window.setInterval(async () => {
      try {
        const now = await getMaintenance()
        if (!now.active) window.location.reload()
        else setState(now)
      } catch {
        /* still down: keep waiting */
      }
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [state?.active])

  if (!state?.active) return null

  const until = state.until
    ? new Date(state.until).toLocaleTimeString(i18n.language, {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  return (
    <Overlay fixed color="var(--hb-page)" backgroundOpacity={1} zIndex={10000}>
      <Center h="100vh" p="md">
        <Paper withBorder shadow="md" p="xl" maw={440} ta="center">
          <Stack align="center" gap="md">
            <IconTool size={40} color="var(--mantine-primary-color-filled)" />
            <Text fz={20} fw={700}>
              {t('app.maintenance.title', 'Wartungsarbeiten')}
            </Text>
            <Text size="sm" lh={1.5}>
              {state.message ||
                t(
                  'app.maintenance.text',
                  'Hubra wird gerade aktualisiert. In wenigen Minuten geht es weiter.',
                )}
            </Text>
            {until && (
              <Text size="sm" c="dimmed">
                {t('app.maintenance.until', 'Voraussichtlich zurück um {{time}} Uhr.', {
                  time: until,
                })}
              </Text>
            )}
            <Text size="xs" c="dimmed">
              {t('app.maintenance.reload', 'Diese Seite lädt sich von selbst neu.')}
            </Text>
            <Anchor
              size="sm"
              href={`${ssoUrl}/status${URL_CLUB ? `?club=${encodeURIComponent(URL_CLUB)}` : ''}`}
            >
              {t('app.maintenance.status', 'Systemstatus')}
            </Anchor>
          </Stack>
        </Paper>
      </Center>
    </Overlay>
  )
}
