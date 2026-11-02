import { useEffect, useState } from 'react'
import { CloseButton, Group, Text } from '@mantine/core'
import { IconTool } from '@tabler/icons-react'
import { getMaintenance, type MaintenanceState } from '@hubra/api-client'
import { useT } from '@/locales/i18n'

const DISMISSED_KEY = 'hubra.maintenanceNotice.dismissed'
const POLL_MS = 10 * 60_000

type Upcoming = NonNullable<MaintenanceState['upcoming']>

function readDismissed(): string | null {
  try {
    return localStorage.getItem(DISMISSED_KEY)
  } catch {
    return null
  }
}

/**
 * Planned maintenance, from the platform's notice period until it starts
 * (manage › Warnungen › Geplante Wartungen). Hidden per window once closed.
 */
export function MaintenanceNotice() {
  const { t, i18n } = useT()
  const [upcoming, setUpcoming] = useState<Upcoming | null>(null)
  const [dismissed, setDismissed] = useState(readDismissed)

  useEffect(() => {
    const ctrl = new AbortController()
    const load = () =>
      getMaintenance(ctrl.signal)
        .then((s) => setUpcoming(s.upcoming ?? null))
        .catch(() => {})
    load()
    const timer = window.setInterval(load, POLL_MS)
    return () => {
      ctrl.abort()
      window.clearInterval(timer)
    }
  }, [])

  if (!upcoming || dismissed === String(upcoming.id)) return null

  const start = new Date(upcoming.starts_at)
  const end = new Date(upcoming.ends_at)
  const day = (d: Date) =>
    d.toLocaleDateString(i18n.language, { weekday: 'short', day: 'numeric', month: 'long' })
  const time = (d: Date) => d.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })
  const sameDay = start.toDateString() === end.toDateString()
  const when = sameDay
    ? t('shell.maintenanceNotice.sameDay', '{{day}}, {{from}} bis {{to}} Uhr', {
        day: day(start),
        from: time(start),
        to: time(end),
      })
    : t('shell.maintenanceNotice.days', '{{fromDay}}, {{from}} bis {{toDay}}, {{to}} Uhr', {
        fromDay: day(start),
        from: time(start),
        toDay: day(end),
        to: time(end),
      })

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, String(upcoming.id))
    } catch {
      // private mode: hide for this page view only
    }
    setDismissed(String(upcoming.id))
  }

  return (
    <Group
      role="status"
      gap={10}
      wrap="nowrap"
      px={16}
      py={8}
      style={{
        background: 'var(--hb-notice-bg)',
        borderBottom: '1px solid var(--hb-notice-border)',
      }}
    >
      <IconTool size={18} color="var(--mantine-color-orange-text)" style={{ flexShrink: 0 }} />
      <Text fz="sm" style={{ flex: 1 }}>
        <Text span fw={600}>
          {t('shell.maintenanceNotice.title', 'Geplante Wartung')}: {when}.
        </Text>{' '}
        {upcoming.message ||
          t(
            'shell.maintenanceNotice.default',
            'In dieser Zeit ist die App nicht erreichbar.',
          )}
      </Text>
      <CloseButton
        size="sm"
        aria-label={t('shell.maintenanceNotice.dismiss', 'Hinweis ausblenden')}
        onClick={dismiss}
      />
    </Group>
  )
}
