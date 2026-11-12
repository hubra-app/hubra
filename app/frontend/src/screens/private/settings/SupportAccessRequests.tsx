import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, Stack, Text } from '@mantine/core'
import { decideSupportAccess, listSupportAccess, type SupportAccessRequest } from '@/api/admin'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { useT } from '@/locales/i18n'

const STATUS_COLOR: Record<SupportAccessRequest['status'], string> = {
  pending: 'orange',
  approved: 'green',
  declined: 'red',
  used: 'gray',
  expired: 'gray',
}

/**
 * Hubra staff's requests to open the club (Settings › Club, under "Hubra
 * support"): open ones can be approved or declined, older ones show who
 * decided. Every start and end of a support session is in the audit log.
 */
export function SupportAccessRequests() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<number | null>(null)
  const query = useQuery({ queryKey: qk.settings.supportAccess, queryFn: listSupportAccess })
  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) => decideSupportAccess(id, approve),
    onMutate: ({ id }) => setBusy(id),
    onSettled: () => setBusy(null),
    onSuccess: (req) => {
      notify(
        'success',
        req.status === 'approved'
          ? t('supportAccess.approved', 'Zugriff freigegeben')
          : t('supportAccess.declined', 'Zugriff abgelehnt'),
      )
      void queryClient.invalidateQueries({ queryKey: qk.settings.supportAccess })
    },
    onError: (err) => notify('error', t('supportAccess.failed', 'Nicht gespeichert'), (err as Error).message),
  })

  const requests = query.data?.requests ?? []
  if (requests.length === 0) {
    return (
      <Text size="xs" c="dimmed" data-testid="support-access-empty">
        {t('supportAccess.none', 'Noch keine Anfragen vom Hubra-Support.')}
      </Text>
    )
  }

  const statusLabel = (s: SupportAccessRequest['status']) =>
    ({
      pending: t('supportAccess.status.pending', 'Offen'),
      approved: t('supportAccess.status.approved', 'Freigegeben'),
      declined: t('supportAccess.status.declined', 'Abgelehnt'),
      used: t('supportAccess.status.used', 'Genutzt'),
      expired: t('supportAccess.status.expired', 'Abgelaufen'),
    })[s]

  return (
    <Stack gap="xs" data-testid="support-access-requests">
      {requests.map((req) => (
        <Paper key={req.id} withBorder p="sm" radius="md">
          <Group justify="space-between" align="flex-start" wrap="wrap" gap="xs">
            <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
              <Group gap={6} wrap="wrap">
                <Text fw={600} size="sm">
                  {req.staff ?? t('supportAccess.staff', 'Hubra-Support')}
                </Text>
                <Badge size="sm" variant="light" color={STATUS_COLOR[req.status]}>
                  {statusLabel(req.status)}
                </Badge>
              </Group>
              <Text size="sm">{req.reason}</Text>
              <Text size="xs" c="dimmed">
                {[
                  req.createdAt ? formatDateTime(req.createdAt) : null,
                  t('supportAccess.minutes', '{{count}} Min.', { count: req.minutes }),
                  req.allowChanges
                    ? t('supportAccess.mayChange', 'darf Änderungen machen')
                    : t('supportAccess.lookOnly', 'nur ansehen'),
                  req.decidedBy
                    ? t('supportAccess.decidedBy', 'entschieden von {{name}}', { name: req.decidedBy })
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </Text>
            </Stack>
            {req.status === 'pending' && (
              <Group gap="xs">
                <Button
                  size="xs"
                  variant="default"
                  loading={busy === req.id && decide.variables?.approve === false}
                  disabled={busy !== null}
                  onClick={() => decide.mutate({ id: req.id, approve: false })}
                >
                  {t('supportAccess.decline', 'Ablehnen')}
                </Button>
                <Button
                  size="xs"
                  loading={busy === req.id && decide.variables?.approve === true}
                  disabled={busy !== null}
                  onClick={() => decide.mutate({ id: req.id, approve: true })}
                  data-testid="support-access-approve"
                >
                  {t('supportAccess.approve', 'Freigeben')}
                </Button>
              </Group>
            )}
          </Group>
        </Paper>
      ))}
    </Stack>
  )
}
