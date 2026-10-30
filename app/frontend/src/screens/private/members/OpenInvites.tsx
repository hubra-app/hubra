import { useState } from 'react'
import { Badge, Button, Group, Paper, Text, UnstyledButton } from '@mantine/core'
import { IconChevronDown, IconChevronRight, IconMailForward } from '@tabler/icons-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelInvite, listInvites, resendInvite, type OpenInvite } from '@/api/members'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { useT } from '@/locales/i18n'

/** Invites nobody accepted yet: see them, send them again or withdraw them. */
export function OpenInvites() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<number | null>(null)
  const { data: invites = [] } = useQuery({
    queryKey: qk.members.invites,
    queryFn: listInvites,
  })

  if (invites.length === 0) return null

  const run = async (invite: OpenInvite, action: 'resend' | 'cancel') => {
    setBusy(invite.id)
    try {
      if (action === 'resend') {
        await resendInvite(invite.id)
        notify(
          'success',
          t('members.invite.sentTitle', 'Einladung gesendet'),
          t('members.invite.sent', '{{email}} erhält einen Link zum Beitreten.', {
            email: invite.email,
          }),
        )
      } else {
        await cancelInvite(invite.id)
        notify('success', t('members.invites.cancelled', 'Einladung zurückgezogen'))
      }
      queryClient.invalidateQueries({ queryKey: qk.members.invites })
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder radius="lg" mb={16}>
      <UnstyledButton
        onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '12px 16px' }}
        aria-expanded={open}
      >
        {open ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
        <IconMailForward size={16} style={{ color: 'var(--hb-text-2)' }} />
        <Text fw={600} fz="sm" style={{ flex: 1 }}>
          {t('members.invites.title', 'Offene Einladungen')}
        </Text>
        <Badge variant="light" color="gray" radius="xl">
          {invites.length}
        </Badge>
      </UnstyledButton>
      {open &&
        invites.map((inv) => (
          <Group
            key={inv.id}
            justify="space-between"
            wrap="wrap"
            gap="xs"
            px="md"
            py={10}
            style={{ borderTop: '1px solid var(--hb-border)' }}
          >
            <div style={{ minWidth: 0 }}>
              <Text fz="sm" fw={500} truncate>
                {inv.email}
              </Text>
              <Text fz="xs" c={inv.expired ? 'red' : 'dimmed'}>
                {inv.expired
                  ? t('members.invites.expired', 'Abgelaufen am {{date}}', {
                      date: formatDate(inv.expiresAt),
                    })
                  : t('members.invites.sentOn', 'Gesendet am {{date}}, gültig bis {{until}}', {
                      date: formatDate(inv.createdAt),
                      until: formatDate(inv.expiresAt),
                    })}
              </Text>
            </div>
            <Group gap="xs" wrap="nowrap">
              <Button
                size="xs"
                variant="default"
                loading={busy === inv.id}
                onClick={() => run(inv, 'resend')}
              >
                {t('members.invites.resend', 'Erneut senden')}
              </Button>
              <Button
                size="xs"
                variant="subtle"
                color="red"
                disabled={busy === inv.id}
                onClick={() => run(inv, 'cancel')}
              >
                {t('members.invites.cancel', 'Zurückziehen')}
              </Button>
            </Group>
          </Group>
        ))}
    </Paper>
  )
}
