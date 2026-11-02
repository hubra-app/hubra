import { useEffect, useState } from 'react'
import { CloseButton, Group, Text } from '@mantine/core'
import { IconTool } from '@tabler/icons-react'
import { getMaintenance, type MaintenanceState } from '@hubra/api-client'
import { useT } from '@/locales/i18n'

const DISMISSED_KEY = 'hubra.maintenanceBanner.dismissed'
const POLL_MS = 5 * 60_000

type Planned = NonNullable<MaintenanceState['planned']>

function readDismissed(): string | null {
  try {
    return sessionStorage.getItem(DISMISSED_KEY)
  } catch {
    return null
  }
}

/**
 * Announced maintenance (platform admins: /wartung planen in Discord, or
 * manage). Shows the start and expected length until it begins; then the
 * maintenance page takes over. Hidden for the session once dismissed.
 */
export function MaintenanceBanner() {
  const { t, i18n } = useT()
  const [planned, setPlanned] = useState<Planned | null>(null)
  const [dismissed, setDismissed] = useState(readDismissed)

  useEffect(() => {
    const ctrl = new AbortController()
    const load = () =>
      getMaintenance(ctrl.signal)
        .then((s) => setPlanned(s.planned ?? null))
        .catch(() => {})
    load()
    const timer = window.setInterval(load, POLL_MS)
    return () => {
      ctrl.abort()
      window.clearInterval(timer)
    }
  }, [])

  if (!planned || dismissed === planned.start) return null
  const start = new Date(planned.start)
  if (Number.isNaN(start.getTime())) return null

  const date = start.toLocaleDateString(i18n.language, {
    weekday: 'short',
    day: 'numeric',
    month: 'numeric',
  })
  const time = start.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISSED_KEY, planned.start)
    } catch {
      // private mode: hide for this page view only
    }
    setDismissed(planned.start)
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
      <IconTool size={18} color="var(--mantine-color-gold-text)" style={{ flexShrink: 0 }} />
      <Text fz="sm" style={{ flex: 1 }}>
        <Text span fw={600}>
          {t('app.maintenance.planned', 'Wartung am {{date}} ab {{time}} Uhr', { date, time })}
          {planned.minutes
            ? ` (${t('app.maintenance.plannedFor', 'etwa {{minutes}} Minuten', { minutes: planned.minutes })})`
            : ''}
          .
        </Text>{' '}
        {planned.message ||
          t('app.maintenance.plannedText', 'Hubra ist dann kurz nicht erreichbar.')}
      </Text>
      <CloseButton
        size="sm"
        aria-label={t('shell.clubBanner.dismiss', 'Banner ausblenden')}
        onClick={dismiss}
      />
    </Group>
  )
}
