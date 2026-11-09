import { useState } from 'react'
import { Alert, Button, Group, Paper, Text, Textarea } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconReceiptOff } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { formatCHF, formatDate } from '@/format'
import { confirmMyFee, getMyFee } from '@/api/feeAdjustments'
import { feeAdjustmentLabel } from '@/screens/private/members/feeAdjustment'
import { qk } from '@/data/keys'

/** A member's own fee arrangement (exempt or reduced), and the place to
 *  confirm before its end date that the reason still applies. Hidden for
 *  members who pay the standard fee. */
export function MyFeeCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({ queryKey: qk.account.fee, queryFn: getMyFee })
  const adj = data?.adjustment
  if (!data || !adj) return null
  const per = (cycle: string | null) => t(`tiers.plans.per.${cycle ?? 'yearly'}`, cycle ?? 'yearly')
  // Before the end date the member can confirm (asked or not); once they
  // did, they can still send an update until the board extends it.
  const canConfirm = !!adj.valid_until && !adj.ended

  const confirm = async () => {
    if (!note.trim()) return
    setBusy(true)
    try {
      queryClient.setQueryData(qk.account.fee, await confirmMyFee(note.trim()))
      setNote('')
      notify('success', t('fees.my.sent', 'Danke, der Vorstand wurde informiert'))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : t('common.unknownError'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder mt="md" data-testid="my-fee">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconReceiptOff size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('fees.my.title', 'Dein Mitgliederbeitrag')}
        </Text>
      </Group>
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {adj.ended ? (
          <Text size="sm">
            {t('fees.my.ended', 'Dein eigener Beitrag ist am {{date}} abgelaufen. Ab der nächsten Periode zahlst du wieder den normalen Beitrag. Trifft der Grund noch zu, melde dich beim Vorstand.', {
              date: formatDate(adj.valid_until!),
            })}
          </Text>
        ) : (
          <Text size="sm">
            <b>{feeAdjustmentLabel(adj, t)}</b>
            {data.amount !== null && data.standard_amount !== null && (
              <>
                {' · '}
                {t('fees.my.instead', 'CHF {{amount}} statt CHF {{standard}} {{per}}', {
                  amount: formatCHF(data.amount),
                  standard: formatCHF(data.standard_amount),
                  per: per(data.billing_cycle),
                })}
              </>
            )}
            {adj.valid_until && (
              <>
                {' · '}
                {t('fees.my.until', 'bis {{date}}', { date: formatDate(adj.valid_until) })}
              </>
            )}
          </Text>
        )}
        <div>
          <Text size="xs" c="dimmed" mb={2}>
            {t('fees.reason', 'Grund')}
          </Text>
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {adj.reason}
          </Text>
        </div>

        {canConfirm && adj.confirmed_at && (
          <Text size="sm" c="dimmed">
            {t('fees.my.confirmedOn', 'Du hast am {{date}} bestätigt, dass der Grund noch zutrifft.', {
              date: formatDate(adj.confirmed_at),
            })}
          </Text>
        )}
        {canConfirm && !adj.confirmed_at && (
          <>
            {adj.awaiting_confirmation && (
              <Alert color="yellow" variant="light" p="sm">
                {t('fees.my.asked', 'Bitte bestätige bis {{date}}, dass der Grund für deinen Beitrag noch zutrifft, zum Beispiel mit einem kurzen Hinweis auf einen aktuellen Nachweis.', {
                  date: formatDate(adj.valid_until!),
                })}
              </Alert>
            )}
            <Textarea
              rows={2}
              value={note}
              maxLength={2000}
              onChange={(e) => setNote(e.currentTarget.value)}
              placeholder={t('fees.my.notePlaceholder', 'z. B. «Studium bis Sommer 2027, Legi sende ich per Mail»')}
              aria-label={t('fees.my.noteLabel', 'Deine Bestätigung')}
              data-testid="my-fee-note"
            />
            <Group justify="flex-end">
              <Button onClick={confirm} disabled={busy || !note.trim()} data-testid="my-fee-confirm">
                {t('fees.my.confirm', 'Grund trifft noch zu')}
              </Button>
            </Group>
          </>
        )}
      </div>
    </Paper>
  )
}
