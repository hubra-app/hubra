import { useState } from 'react'
import { Button, Group, Paper, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconDoorExit } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { Modal } from '@/components/ui'
import { getMyLeave, leaveClub, withdrawLeaveRequest } from '@/api/members'
import { formatDate } from '@/format'
import { qk } from '@/data/keys'

/** Leave the club, or ask to leave when the club approves it. */
export function LeaveClubCard() {
  const { t } = useT()
  const { notify } = useToast()
  const { ssoUrl } = useInstance()
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const { data: leave } = useQuery({ queryKey: qk.account.leave, queryFn: getMyLeave })
  if (!leave) return null

  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.error'),
      err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
    )

  const confirm = async () => {
    setBusy(true)
    try {
      const res = await leaveClub()
      setConfirming(false)
      if (res.status === 'left') {
        // No club pages any more: back to the club list.
        window.location.assign(`${ssoUrl}/clubs`)
        return
      }
      queryClient.invalidateQueries({ queryKey: qk.account.leave })
      notify(
        'success',
        t('account.leaveClub.requested', 'Austritt beantragt'),
        t('account.leaveClub.requestedMsg', 'Die Vereinsleitung bestätigt deinen Austritt.'),
      )
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  const withdraw = async () => {
    setBusy(true)
    try {
      await withdrawLeaveRequest()
      queryClient.invalidateQueries({ queryKey: qk.account.leave })
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        <IconDoorExit size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.leaveClub.title', 'Verein verlassen')}
        </Text>
      </Group>
      <Group p="md" justify="space-between" wrap="wrap" gap="sm">
        <Text fz="sm" c="dimmed" style={{ flex: 1, minWidth: 220 }}>
          {leave.requestedAt
            ? t('account.leaveClub.pending', {
                defaultValue: 'Du hast am {{date}} den Austritt beantragt. Die Vereinsleitung bestätigt ihn.',
                date: formatDate(leave.requestedAt),
              })
            : leave.requiresApproval
              ? t('account.leaveClub.needsApproval', 'Dein Austritt wird wirksam, sobald die Vereinsleitung ihn bestätigt.')
              : t('account.leaveClub.atOnce', 'Du verlässt den Verein sofort. Dein Hubra-Konto und deine anderen Vereine bleiben.')}
        </Text>
        {leave.requestedAt ? (
          <Button variant="default" onClick={withdraw} loading={busy}>
            {t('account.leaveClub.withdraw', 'Antrag zurückziehen')}
          </Button>
        ) : (
          <Button variant="light" color="red" onClick={() => setConfirming(true)}>
            {leave.requiresApproval
              ? t('account.leaveClub.request', 'Austritt beantragen')
              : t('account.leaveClub.title', 'Verein verlassen')}
          </Button>
        )}
      </Group>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title={t('account.leaveClub.confirmTitle', 'Verein wirklich verlassen?')}
        footer={
          <>
            <Button variant="default" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
            <Button color="red" onClick={confirm} loading={busy}>
              {leave.requiresApproval
                ? t('account.leaveClub.request', 'Austritt beantragen')
                : t('account.leaveClub.title', 'Verein verlassen')}
            </Button>
          </>
        }
      >
        <Text fz="sm">
          {t(
            'account.leaveClub.confirmBody',
            'Du verlierst den Zugang zu den Seiten des Vereins. Deine Rechnungen und Einträge bleiben beim Verein. Möchtest du später zurück, kannst du wieder um Aufnahme bitten.',
          )}
        </Text>
      </Modal>
    </Paper>
  )
}
