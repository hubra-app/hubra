import { useState, useEffect } from 'react'
import { Badge, Button, Group, Text } from '@mantine/core'
import { IconAlertTriangle, IconX } from '@tabler/icons-react'
import { useAuth } from '@/context/AppContext'

export function ImpersonationBanner() {
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

    const interval = setInterval(() => setRemainingMin(compute()), 60000)
    return () => clearInterval(interval)

  }, [impersonation?.expires_at, impersonation?.is_impersonating])

  if (!impersonation?.is_impersonating) return null

  return (
    <div
      style={{
        background: '#fef3c7',
        borderBottom: '1px solid #f59e0b',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        zIndex: 100,
      }}
    >
      <IconAlertTriangle size={20} color="#d97706" />
      <Badge color="orange" variant="filled" size="sm">
        Impersonating
      </Badge>
      <Text fz="sm" fw={600}>
        Acting as tenant: {impersonation.tenant_slug}
      </Text>
      {impersonation.reason && (
        <Text fz="xs" c="dimmed">
          Reason: {impersonation.reason}
        </Text>
      )}
      {remainingMin !== null && (
        <Text fz="xs" c="dimmed">
          {remainingMin} min remaining
        </Text>
      )}
      <Group gap={6} style={{ marginLeft: 'auto' }}>
        <Button
          size="xs"
          variant="filled"
          color="orange"
          leftSection={<IconX size={14} />}
          onClick={stopImpersonation}
        >
          Stop Impersonating
        </Button>
      </Group>
    </div>
  )
}
