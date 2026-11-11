import { useState, type FormEvent } from 'react'
import { Button, NumberInput, SimpleGrid, Text, TextInput, Textarea } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconReceiptOff } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { formatCHF, formatDate } from '@/format'
import { ConfirmModal, Modal, Field, Seg, Tag } from '@/components/ui'
import { DetailRow, DetailSection, DetailEmpty } from '@/components/detail'
import {
  getMemberFee,
  removeMemberFee,
  setMemberFee,
  type FeeAdjustment,
  type FeeAdjustmentKind,
  type MemberFee,
} from '@/api/feeAdjustments'
import { qk } from '@/data/keys'
import { feeAdjustmentLabel } from './feeAdjustment'

/** Where the arrangement stands: running, asked, confirmed, ended. */
export function FeeAdjustmentStatus({ adj }: { adj: FeeAdjustment }) {
  const { t } = useT()
  if (adj.ended) return <Tag color="var(--mantine-color-red-text)">{t('fees.status.ended', 'Abgelaufen')}</Tag>
  if (adj.confirmed_at)
    return (
      <Tag color="var(--mantine-color-green-text)">
        {t('fees.status.confirmed', 'Bestätigt am {{date}}', { date: formatDate(adj.confirmed_at) })}
      </Tag>
    )
  if (adj.awaiting_confirmation)
    return <Tag color="var(--mantine-color-yellow-text)">{t('fees.status.asked', 'Bestätigung angefragt')}</Tag>
  return <Tag>{t('fees.status.running', 'Läuft')}</Tag>
}

/** The member page's card about their membership fee: the standard fee and,
 *  when the board set one, their own (exempt, own amount or a reduction)
 *  with reason, end date and the member's confirmation. */
export function MemberFeeSection({ memberId, memberName }: { memberId: string; memberName: string }) {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const canRead = hasPermission('tiers.fee_adjustments.read')
  const canUpdate = hasPermission('tiers.fee_adjustments.update')
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const [editing, setEditing] = useState(false)
  const [removing, setRemoving] = useState(false)
  const { data } = useQuery({
    queryKey: qk.members.fee(memberId),
    queryFn: () => getMemberFee(memberId),
    enabled: canRead,
  })
  if (!canRead || !data) return null
  const adj = data.adjustment
  const per = (cycle: string | null) => t(`tiers.plans.per.${cycle ?? 'yearly'}`, cycle ?? 'yearly')

  const refresh = (next: MemberFee) => {
    queryClient.setQueryData(qk.members.fee(memberId), next)
    queryClient.invalidateQueries({ queryKey: qk.tiers.feeAdjustments })
  }

  const remove = async () => {
    try {
      refresh(await removeMemberFee(memberId))
      notify('success', t('fees.removed', 'Zahlt wieder den normalen Beitrag'))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : t('common.unknownError'))
    } finally {
      setRemoving(false)
    }
  }

  return (
    <>
      <DetailSection
        icon={<IconReceiptOff size={16} />}
        title={t('fees.title', 'Mitgliederbeitrag')}
        right={
          canUpdate ? (
            <Button size="compact-sm" variant="subtle" onClick={() => setEditing(true)} data-testid="fee-edit">
              {adj ? t('common.edit') : t('fees.adjust', 'Anpassen')}
            </Button>
          ) : undefined
        }
      >
        <DetailRow label={t('fees.standard', 'Normaler Beitrag')} mono>
          {data.standard_amount === null ? (
            <DetailEmpty />
          ) : (
            `CHF ${formatCHF(data.standard_amount)} ${per(data.billing_cycle)}`
          )}
        </DetailRow>
        {adj ? (
          <>
            <DetailRow label={t('fees.own', 'Eigener Beitrag')}>
              <span data-testid="fee-own">{feeAdjustmentLabel(adj, t)}</span>
            </DetailRow>
            {data.amount !== null && adj.active && (
              <DetailRow label={t('fees.pays', 'Bezahlt')} mono>
                {`CHF ${formatCHF(data.amount)} ${per(data.billing_cycle)}`}
              </DetailRow>
            )}
            <DetailRow label={t('fees.until', 'Gültig bis')}>
              {adj.valid_until ? formatDate(adj.valid_until) : t('fees.noEnd', 'Unbefristet')}
            </DetailRow>
            <DetailRow label={t('common.status')}>
              <FeeAdjustmentStatus adj={adj} />
            </DetailRow>
            <div style={{ padding: '10px 16px', borderTop: '1px solid var(--hb-border)' }}>
              <Text size="xs" c="dimmed" mb={4}>
                {t('fees.reason', 'Grund')}
              </Text>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {adj.reason}
              </Text>
              {adj.confirmation_note && (
                <>
                  <Text size="xs" c="dimmed" mt={10} mb={4}>
                    {t('fees.memberNote', 'Antwort des Mitglieds')}
                  </Text>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap' }} data-testid="fee-member-note">
                    {adj.confirmation_note}
                  </Text>
                </>
              )}
            </div>
          </>
        ) : (
          <DetailRow label={t('fees.own', 'Eigener Beitrag')} borderless>
            <Text span size="sm" c="dimmed">
              {t('fees.none', 'Keiner, zahlt den normalen Beitrag')}
            </Text>
          </DetailRow>
        )}
      </DetailSection>

      {editing && (
        <FeeAdjustmentModal
          memberId={memberId}
          memberName={memberName}
          current={adj}
          onClose={() => setEditing(false)}
          onSaved={(next) => {
            refresh(next)
            setEditing(false)
          }}
          onRemove={adj ? () => {
            setEditing(false)
            setRemoving(true)
          } : undefined}
        />
      )}
      <ConfirmModal
        open={removing}
        onClose={() => setRemoving(false)}
        title={t('fees.removeTitle', 'Eigenen Beitrag entfernen?')}
        body={t('fees.removeBody', '{{name}} zahlt ab der nächsten Rechnung wieder den normalen Beitrag.', {
          name: memberName,
        })}
        confirmLabel={t('fees.remove', 'Entfernen')}
        cancelLabel={t('common.cancel')}
        onConfirm={remove}
      />
    </>
  )
}

function FeeAdjustmentModal({
  memberId,
  memberName,
  current,
  onClose,
  onSaved,
  onRemove,
}: {
  memberId: string
  memberName: string
  current: FeeAdjustment | null
  onClose: () => void
  onSaved: (next: MemberFee) => void
  onRemove?: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [kind, setKind] = useState<FeeAdjustmentKind>(current?.kind ?? 'exempt')
  const [amount, setAmount] = useState<number | string>(current?.amount_chf ?? '')
  const [percent, setPercent] = useState<number | string>(current?.percent ?? 50)
  const [reason, setReason] = useState(current?.reason ?? '')
  const [until, setUntil] = useState(current?.valid_until ?? '')
  const [remindDays, setRemindDays] = useState<number | string>(current?.remind_days ?? 30)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const save = async (event?: FormEvent) => {
    event?.preventDefault()
    const next: Record<string, string> = {}
    if (!reason.trim()) next.reason = t('fees.reasonRequired', 'Bitte gib einen Grund an')
    if (kind === 'amount' && (amount === '' || Number(amount) < 0))
      next.amount = t('fees.amountRequired', 'Bitte gib einen Betrag an')
    if (kind === 'percent' && (percent === '' || Number(percent) < 0 || Number(percent) > 100))
      next.percent = t('fees.percentRange', 'Zwischen 0 und 100')
    setErrors(next)
    if (Object.keys(next).length) return
    setSaving(true)
    try {
      const saved = await setMemberFee(memberId, {
        kind,
        amount_chf: kind === 'amount' ? Number(amount) : null,
        percent: kind === 'percent' ? Number(percent) : null,
        reason: reason.trim(),
        valid_until: until || null,
        remind_days: Number(remindDays) || 0,
      })
      notify('success', t('fees.saved', 'Beitrag gespeichert'))
      onSaved(saved)
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : t('common.unknownError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={save}
      title={t('fees.modalTitle', 'Eigener Mitgliederbeitrag')}
      subtitle={memberName}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="filled" type="submit" disabled={saving} data-testid="fee-save">
            {t('common.save', 'Speichern')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Field label={t('fees.kindLabel', 'Art')}>
          <Seg
            value={kind}
            onChange={(v) => setKind(v as FeeAdjustmentKind)}
            options={[
              { value: 'exempt', label: t('fees.kind.exempt', 'Befreit') },
              { value: 'amount', label: t('fees.kind.amount', 'Eigener Betrag') },
              { value: 'percent', label: t('fees.kind.percent', 'Ermässigung') },
            ]}
          />
        </Field>
        {kind === 'amount' && (
          <Field
            label={t('fees.amountLabel', 'Beitrag pro Jahr (CHF)')}
            hint={t('fees.amountHint', 'Wird wie der normale Beitrag auf die Rechnungsperioden verteilt.')}
          >
            <NumberInput
              value={amount}
              onChange={setAmount}
              min={0}
              decimalScale={2}
              thousandSeparator="’"
              hideControls
              error={errors.amount}
              data-testid="fee-amount"
            />
          </Field>
        )}
        {kind === 'percent' && (
          <Field label={t('fees.percentLabel', 'Ermässigung in %')}>
            <NumberInput
              value={percent}
              onChange={setPercent}
              min={0}
              max={100}
              decimalScale={2}
              suffix=" %"
              error={errors.percent}
            />
          </Field>
        )}
        <Field
          label={t('fees.reason', 'Grund')}
          hint={t('fees.reasonHint', 'Das Mitglied sieht den Grund in seinem Konto.')}
        >
          <Textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            error={errors.reason}
            maxLength={2000}
            data-testid="fee-reason"
          />
        </Field>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field
            label={t('fees.untilLabel', 'Gültig bis (optional)')}
            hint={t('fees.untilHint', 'Danach gilt ab der nächsten Periode wieder der normale Beitrag.')}
          >
            <TextInput
              type="date"
              value={until}
              onChange={(e) => setUntil(e.currentTarget.value)}
              data-testid="fee-until"
            />
          </Field>
          <Field
            label={t('fees.remindLabel', 'Erinnerung (Tage vorher)')}
            hint={t('fees.remindHint', 'Das Mitglied bestätigt dann, dass der Grund noch zutrifft. 0: keine Erinnerung.')}
          >
            <NumberInput
              value={remindDays}
              onChange={setRemindDays}
              min={0}
              max={365}
              disabled={!until}
            />
          </Field>
        </SimpleGrid>
        {onRemove && (
          <div>
            <Button variant="subtle" color="red" size="compact-sm" px={0} onClick={onRemove}>
              {t('fees.removeShort', 'Zurück zum normalen Beitrag')}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  )
}
