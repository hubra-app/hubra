import { Button, Paper, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { Avatar } from '@/components/ui'
import { listLeaveRequests, approveLeave, declineLeave } from '@/api/members'
import { formatDateTime } from '@/format'

/* ── Requests to leave (clubs that approve them) ───────── */
export function LeaveRequests() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canDecide = hasPermission('members.members.archive')
  const { data: requests = [] } = useQuery({
    queryKey: ['leave-requests'],
    queryFn: listLeaveRequests,
    enabled: canDecide,
  })
  if (!canDecide || requests.length === 0) return null

  const decide = async (id: string, name: string, approve: boolean) => {
    try {
      await (approve ? approveLeave(id) : declineLeave(id))
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] })
      queryClient.invalidateQueries({ queryKey: ['members'] })
      notify(
        approve ? 'success' : 'info',
        approve
          ? t('members.leave.approved', 'Austritt bestätigt')
          : t('members.leave.declined', 'Austritt abgelehnt'),
        name,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg" mt="lg">
      <Text fw={700} fz="md" px={20} pt={16} pb={8}>
        {t('members.leave.requestsTitle', 'Austrittsgesuche')}
      </Text>
      {requests.map((r) => (
        <div
          key={r.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '14px 20px',
            borderTop: '1px solid #e6e3ef',
          }}
        >
          <Avatar name={r.name} color={r.avatarColor} size={38} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 'var(--mantine-font-size-sm)', fontWeight: 600 }}>{r.name}</div>
            <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#5e5873' }}>
              {r.email} · {t('members.leave.wantsToLeave', 'möchte austreten')}
            </div>
          </div>
          <span className="num" style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#8c86a0' }}>
            {formatDateTime(r.requestedAt)}
          </span>
          <Button size="sm" variant="default" onClick={() => decide(r.id, r.name, false)}>
            {t('members.leave.decline', 'Ablehnen')}
          </Button>
          <Button size="sm" variant="filled" color="red" onClick={() => decide(r.id, r.name, true)}>
            {t('members.leave.approve', 'Austritt bestätigen')}
          </Button>
        </div>
      ))}
    </Paper>
  )
}
