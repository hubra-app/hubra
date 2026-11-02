import { useState, useEffect } from 'react'
import { Badge, Button, Group, Text } from '@mantine/core'
import { IconAlertTriangle, IconX } from '@tabler/icons-react'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'

export function ImpersonationBanner() {
  const { t } = useT()
  const { impersonation, stopImpersonation } = useAuth()
  const [remainingMin, setRemainingMin] = useState<number | null>(null)

  useEffect(() => {
    const expiresAt = impersonation?.expires_at
    if (!expiresAt || !impersonation?.is_impersonating) {
      return
    }
    const compute = () =>
      Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 60000))
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRemainingMin(compute())

    const interval = setInterval(() => setRemainingMin(compute()), 15000)
    return () => clearInterval(interval)

  }, [impersonation?.expires_at, impersonation?.is_impersonating])

  if (!impersonation?.is_impersonating) return null
  // The last five minutes of a support session: turn red, so nobody is cut
  // off mid-task without warning.
  const ending = remainingMin !== null && remainingMin < 5

  return (
    <div
      role="status"
      style={{
        background: ending ? '#fee2e2' : '#fef3c7',
        borderBottom: `1px solid ${ending ? '#ef4444' : '#f59e0b'}`,
        color: '#1a1625',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '4px 12px',
        zIndex: 100,
      }}
    >
      <IconAlertTriangle size={20} color={ending ? '#dc2626' : '#d97706'} />
      <Badge color={ending ? 'red' : 'orange'} variant="filled" size="sm">
        {t('shell.impersonation.badge', 'Fremdzugriff')}
      </Badge>
      <Text fz="sm" fw={600}>
        {impersonation.read_only
          ? t('shell.impersonation.lookingAt', 'Du siehst den Verein {{club}} nur an', {
              club: impersonation.tenant_slug,
            })
          : t('shell.impersonation.actingAs', 'Du handelst im Verein {{club}}', {
              club: impersonation.tenant_slug,
            })}
      </Text>
      {impersonation.reason && (
        <Text fz="xs" c="dimmed">
          {t('shell.impersonation.reason', 'Grund: {{reason}}', { reason: impersonation.reason })}
        </Text>
      )}
      {remainingMin !== null && (
        <Text fz="xs" fw={ending ? 700 : undefined} c={ending ? '#b91c1c' : 'dimmed'}>
          {t('shell.impersonation.remaining', 'noch {{min}} Min.', { min: remainingMin })}
        </Text>
      )}
      <Group gap={6} style={{ marginLeft: 'auto' }}>
        <Button
          size="xs"
          variant="filled"
          color={ending ? 'red' : 'orange'}
          leftSection={<IconX size={14} />}
          onClick={stopImpersonation}
        >
          {t('shell.impersonation.stop', 'Fremdzugriff beenden')}
        </Button>
      </Group>
    </div>
  )
}
