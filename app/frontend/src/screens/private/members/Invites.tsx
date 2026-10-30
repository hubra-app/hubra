import { useState } from 'react'
import { ActionIcon, Badge, Paper, Text, Tooltip } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconSend, IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { ConfirmModal } from '@/components/ui'
import { listInvites, resendInvite, revokeInvite, type ClubInvite } from '@/api/members'
import { formatDate } from '@/format'
import { qk } from '@/data/keys'

const STATUS_COLOR: Record<ClubInvite['status'], string> = {
  open: 'blue',
  accepted: 'green',
  expired: 'gray',
}

/* ── Invites the club sent and whether they were accepted ───────── */
export function Invites() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canInvite = hasPermission('members.members.create')
  const [busy, setBusy] = useState<number | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<ClubInvite | null>(null)
  const { data: invites = [] } = useQuery({
    queryKey: qk.invites,
    queryFn: listInvites,
    enabled: canInvite,
  })
  if (!canInvite || invites.length === 0) return null

  const run = async (invite: ClubInvite, action: 'resend' | 'revoke') => {
    setBusy(invite.id)
    try {
      if (action === 'resend') {
        await resendInvite(invite.id)
        notify(
          'success',
          t('members.invite.sentTitle', 'Einladung gesendet'),
          t('members.invite.sent', '{{email}} erhält einen Link zum Beitreten.', { email: invite.email }),
        )
      } else {
        await revokeInvite(invite.id)
        notify('info', t('members.invites.revoked', 'Einladung zurückgezogen'), invite.email)
      }
      queryClient.invalidateQueries({ queryKey: qk.invites })
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setBusy(null)
    }
  }

  const statusLabel = (i: ClubInvite) =>
    i.status === 'accepted'
      ? t('members.invites.accepted', 'Angenommen')
      : i.status === 'expired'
        ? t('members.invites.expired', 'Abgelaufen')
        : t('members.invites.open', 'Offen')

  const detail = (i: ClubInvite) =>
    i.status === 'accepted' && i.acceptedAt
      ? t('members.invites.acceptedOn', 'angenommen am {{date}}', { date: formatDate(i.acceptedAt) })
      : i.status === 'open'
        ? t('members.invites.validUntil', 'gültig bis {{date}}', { date: formatDate(i.expiresAt) })
        : t('members.invites.expiredOn', 'abgelaufen am {{date}}', { date: formatDate(i.expiresAt) })

  return (
    <Paper withBorder shadow="sm" radius="lg" mt="lg">
      <Text fw={700} fz="md" px={20} pt={16} pb={8}>
        {t('members.invites.title', 'Einladungen')}
      </Text>
      {invites.map((i) => (
        <div
          key={i.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 10,
            padding: '12px 20px',
            borderTop: '1px solid var(--hb-border)',
          }}
        >
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {i.email}
            </div>
            <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-2)' }}>
              {t('members.invites.sentBy', 'von {{name}} am {{date}}', {
                name: i.invitedBy,
                date: formatDate(i.createdAt),
              })}{' '}
              · {detail(i)}
            </div>
          </div>
          <Badge variant="light" radius="xl" color={STATUS_COLOR[i.status]}>
            {statusLabel(i)}
          </Badge>
          {i.status !== 'accepted' && (
            <Tooltip label={t('members.invites.resend', 'Erneut senden')}>
              <ActionIcon
                variant="subtle"
                size="md"
                loading={busy === i.id}
                onClick={() => run(i, 'resend')}
                aria-label={t('members.invites.resend', 'Erneut senden')}
              >
                <IconSend size={18} />
              </ActionIcon>
            </Tooltip>
          )}
          {i.status === 'open' && (
            <Tooltip label={t('members.invites.revoke', 'Zurückziehen')}>
              <ActionIcon
                variant="subtle"
                color="red"
                size="md"
                disabled={busy === i.id}
                onClick={() => setRevokeTarget(i)}
                aria-label={t('members.invites.revoke', 'Zurückziehen')}
              >
                <IconX size={18} />
              </ActionIcon>
            </Tooltip>
          )}
        </div>
      ))}
      <ConfirmModal
        open={!!revokeTarget}
        onClose={() => setRevokeTarget(null)}
        title={t('members.invites.revokeTitle', 'Einladung zurückziehen?')}
        body={t('members.invites.revokeBody', 'Der Link an {{email}} funktioniert danach nicht mehr.', {
          email: revokeTarget?.email ?? '',
        })}
        onConfirm={() => {
          if (revokeTarget) run(revokeTarget, 'revoke')
        }}
      />
    </Paper>
  )
}
