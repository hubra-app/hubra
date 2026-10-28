import { useState, useEffect, useMemo } from 'react'
import { Button, Group, Select, Paper, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconPencil, IconTrash } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import {
  Modal,
  Field,
  ConfirmModal,
  MemberSlideOver,
  type SlideOverMember,
} from '@/components/ui'
import type { MembershipTier } from '@/types'
import type { TierCostPreview } from '@/api/tiers'
import {
  listTiers,
  createTier,
  updateTier,
  deleteTier,
  calculateTierCost,
} from '@/api/tiers'
import { listTierMembers, updateMember } from '@/api/members'
import { PaymentPlansEditor } from './PaymentPlansEditor'
import { useMemberSearch } from '@/data/members'

type Translate = ReturnType<typeof useT>['t']

/** Builds the price line locally so the billing period is translated. */
function costSummary(
  t: Translate,
  cost: Pick<TierCostPreview, 'amount' | 'period'> | undefined,
): string | undefined {
  if (!cost) return undefined
  if (!(cost.amount > 0)) return '—'
  const period = t(`tiers.per.${cost.period ?? 'period'}`, cost.period ?? 'Periode')
  return `CHF ${cost.amount.toFixed(2)} / ${period}`
}

/* -- Tier Detail Panel ------------------------- */
function TierDetailPanel({
  tier,
  onClose,
  onMemberMoved,
  costSummary,
}: {
  tier: MembershipTier
  onClose: () => void
  onMemberMoved?: () => void
  costSummary?: string
}) {
  const { notify } = useToast()
  const { t } = useT()
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const { data: members = [], isLoading: loading } = useQuery({
    queryKey: ['tier-members', tier.id],
    queryFn: () => listTierMembers(tier.id),
  })
  const { data: searchData } = useMemberSearch(searchQuery, { enabled: searchQuery.length >= 2 })

  const slideMembers: SlideOverMember[] = useMemo(
    () =>
      members.map((m) => ({
        id: m.id,
        name: m.name,
        email: m.email,
        avatarColor: m.avatarColor,
        tier: m.tier,
      })),
    [members],
  )

  const searchResults = useMemo(() => {
    if (!searchData || searchQuery.length < 2) return undefined
    const inTier = new Set(members.map((m) => m.id))
    return searchData.members
      .filter((m) => !inTier.has(m.id))
      .map((m) => ({
        id: m.id,
        name: m.name,
        email: m.email,
        avatarColor: m.avatarColor,
        tier: m.tier,
      }))
  }, [searchData, members, searchQuery])

  const handleAdd = (m: SlideOverMember) => {
    updateMember(m.id, { tierName: tier.name })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ['tier-members', tier.id] })
        notify('success', t('tiers.updated', 'Stufe aktualisiert'), t('tiers.memberMoved', '{{member}} ist jetzt in {{tier}}.', { member: m.name, tier: tier.name }))
        onMemberMoved?.()
      })
      .catch((err: unknown) =>
        notify(
          'error',
          t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
          err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
        ),
      )
  }

  return (
    <MemberSlideOver
      title={tier.name}
      subtitle={costSummary ?? '—'}
      icon={
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: 3,
            background: tier.color ?? '#7441e0',
          }}
        />
      }
      members={slideMembers}
      loading={loading}
      addLabel={t('tiers.moveMember', 'Mitglied in diese Stufe verschieben')}
      addPlaceholder={t('tiers.searchMembers', 'Mitglieder suchen …')}
      searchResults={searchResults}
      onAdd={handleAdd}
      onAddSearch={setSearchQuery}
      onClose={onClose}
    />
  )
}

/* -- Membership tiers -------------------------- */
const makeTierSchema = (t: Translate) => z.object({
  name: z.string().min(1, t('common.nameRequired', 'Name ist erforderlich')),
  color: z.string(),
  priceType: z.enum(['fixed', 'percentage', 'formula']),
  billingCycle: z.string(),
  price: z.string(),
  percentageVal: z.string(),
  coefficient: z.string(),
  roundTo: z.string(),
  deductIds: z.array(z.number()),
})
type TierForm = z.infer<ReturnType<typeof makeTierSchema>>

export function TiersTab() {
  const { notify } = useToast()
  const { t } = useT()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('tiers.tiers.create')
  const canUpdate = hasPermission('tiers.tiers.update')
  const canDelete = hasPermission('tiers.tiers.delete')
  const { data: tiers = [] } = useQuery({
    queryKey: ['tiers'],
    queryFn: () => listTiers(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<MembershipTier | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<MembershipTier | null>(null)
  const [detailTier, setDetailTier] = useState<MembershipTier | null>(null)
  const [saving, setSaving] = useState(false)
  const { data: tierCosts = {} } = useQuery({
    queryKey: ['tier-costs', tiers],
    queryFn: async () => {
      const costs: Record<string, TierCostPreview> = {}
      await Promise.all(
        tiers.map(async (tier) => {
          try {
            costs[tier.id] = await calculateTierCost({
              priceType: tier.priceType,
              billingCycle: tier.billingCycle,
              priceChf: tier.priceChf,
              percentageValue: tier.percentageValue,
              coefficient: tier.coefficient,
              roundTo: tier.roundTo,
              deductTierIds: tier.deductTierIds,
              tierId: Number(tier.id),
            })
          } catch {
            /* ignore */
          }
        }),
      )
      return costs
    },
    enabled: tiers.length > 0,
  })

  const form = useForm<TierForm>({
    validate: zodResolver(makeTierSchema(t)),
    initialValues: {
      name: '',
      color: '#7441e0',
      priceType: 'fixed',
      billingCycle: '',
      price: '',
      percentageVal: '',
      coefficient: '',
      roundTo: '',
      deductIds: [],
    },
  })

  const watchedPriceType = form.values.priceType
  const watchedBillingCycle = form.values.billingCycle
  const watchedPrice = form.values.price
  const watchedPercentageVal = form.values.percentageVal
  const watchedCoefficient = form.values.coefficient
  const watchedRoundTo = form.values.roundTo
  const watchedDeductIds = form.values.deductIds

  const [costPreview, setCostPreview] = useState<TierCostPreview | null>(null)

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const result = await calculateTierCost({
          priceType: watchedPriceType,
          billingCycle: (watchedBillingCycle || null) as
            | 'monthly'
            | 'yearly'
            | null,
          priceChf: watchedPrice ? Number(watchedPrice) : null,
          percentageValue: watchedPercentageVal
            ? Number(watchedPercentageVal)
            : null,
          coefficient: watchedCoefficient ? Number(watchedCoefficient) : null,
          roundTo: watchedRoundTo ? Number(watchedRoundTo) : null,
          deductTierIds: watchedDeductIds,
          tierId: editTarget ? Number(editTarget.id) : undefined,
        })
        setCostPreview(result)
      } catch {
        setCostPreview(null)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [
    watchedPriceType,
    watchedBillingCycle,
    watchedPrice,
    watchedPercentageVal,
    watchedCoefficient,
    watchedRoundTo,
    watchedDeductIds,
    editTarget,
  ])

  const openAdd = () => {
    form.setValues({
      name: '',
      color: '#7441e0',
      priceType: 'fixed',
      billingCycle: '',
      price: '',
      percentageVal: '',
      coefficient: '',
      roundTo: '',
      deductIds: [],
    })
    setCostPreview(null)
    setAddOpen(true)
  }
  const openEdit = (tier: MembershipTier) => {
    setEditTarget(tier)
    form.setValues({
      name: tier.name,
      color: tier.color,
      priceType: tier.priceType,
      billingCycle: tier.billingCycle ?? '',
      price: tier.priceChf != null ? String(tier.priceChf) : '',
      percentageVal: tier.percentageValue != null ? String(tier.percentageValue) : '',
      coefficient: tier.coefficient != null ? String(tier.coefficient) : '',
      roundTo: tier.roundTo != null ? String(tier.roundTo) : '',
      deductIds: tier.deductTierIds ?? [],
    })
  }

  const saveAdd = async (data: TierForm) => {
    setSaving(true)
    try {
      await createTier({
        name: data.name,
        color: data.color,
        priceChf: data.price ? Number(data.price) : null,
        billingCycle: (data.billingCycle || null) as
          | 'monthly'
          | 'yearly'
          | null,
        priceType: data.priceType,
        percentageValue: data.percentageVal ? Number(data.percentageVal) : null,
        coefficient: data.coefficient ? Number(data.coefficient) : null,
        roundTo: data.roundTo ? Number(data.roundTo) : null,
        deductTierIds: data.deductIds,
      })
      queryClient.invalidateQueries({ queryKey: ['tiers'] })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setAddOpen(false)
      notify(
        'success',
        t('tiers.created', 'Stufe erstellt'),
        t('tiers.createdMsg', 'Die Stufe {{name}} ist aktiv.', { name: data.name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  const saveEdit = async (data: TierForm) => {
    if (!editTarget) return
    setSaving(true)
    try {
      await updateTier(editTarget.id, {
        name: data.name,
        color: data.color,
        priceChf: data.price ? Number(data.price) : null,
        billingCycle: (data.billingCycle || null) as
          | 'monthly'
          | 'yearly'
          | null,
        priceType: data.priceType,
        percentageValue: data.percentageVal ? Number(data.percentageVal) : null,
        coefficient: data.coefficient ? Number(data.coefficient) : null,
        roundTo: data.roundTo ? Number(data.roundTo) : null,
        deductTierIds: data.deductIds,
      })
      queryClient.invalidateQueries({ queryKey: ['tiers'] })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      setEditTarget(null)
      notify('success', t('tiers.updated', 'Stufe aktualisiert'), t('tiers.updatedMsg', '{{name}} wurde gespeichert.', { name: data.name }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTier(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['tiers'] })
      queryClient.invalidateQueries({ queryKey: ['lookups'] })
      notify('info', t('tiers.deleted', 'Stufe gelöscht'), t('tiers.deletedMsg', '{{name}} wurde entfernt.', { name: deleteTarget.name }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const allTiers = tiers // local alias for tier select options

  const tierForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 72px', gap: 12 }}
      >
        <Field label={t('tiers.form.name', 'Name der Stufe')}>
          <TextInput
            {...form.getInputProps('name')}
            placeholder={t('tiers.form.namePlaceholder', 'z. B. Vollzugang')}
          />
        </Field>
        <Field label={t('common.color', 'Farbe')}>
          <TextInput
            type="color"
            {...form.getInputProps('color')}
            style={{ height: 38, padding: '2px 6px', cursor: 'pointer' }}
          />
        </Field>
      </div>

      <Field label={t('tiers.form.priceType', 'Preisart')}>
        <Select
          data={[
            { value: 'fixed', label: t('tiers.type.fixed', 'Fester Betrag') },
            { value: 'percentage', label: t('tiers.type.percentage', 'Prozentual') },
            { value: 'formula', label: t('tiers.type.formula', 'Formel') },
          ]}
          {...form.getInputProps('priceType')}
        />
      </Field>

      <Field label={t('tiers.form.billingCycle', 'Abrechnung')}>
        <Select
          data={[
            { value: '', label: t('tiers.cycle.none', 'Keine (manuell)') },
            { value: 'monthly', label: t('tiers.cycle.monthly', 'Monatlich') },
            { value: 'yearly', label: t('tiers.cycle.yearly', 'Jährlich') },
          ]}
          {...form.getInputProps('billingCycle')}
        />
      </Field>

      {watchedPriceType === 'fixed' && (
        <Field
          label={t('tiers.form.price', 'Preis (CHF)')}
          hint={t('tiers.form.perPeriod', 'Pro {{period}}', { period: t(`tiers.per.${watchedBillingCycle || 'period'}`, watchedBillingCycle || 'Periode') })}
        >
          <TextInput
            type="number"
            min={0}
            {...form.getInputProps('price')}
            placeholder="80"
          />
        </Field>
      )}

      {watchedPriceType === 'percentage' && (
        <>
          <Field
            label={t('tiers.form.percentage', 'Prozentsatz (%)')}
            hint={t('tiers.form.percentageHint', 'z. B. 2.5 heisst 2.5 % der jährlichen Ausgaben pro Mitglied und Jahr')}
          >
            <TextInput
              type="number"
              min={0}
              step={0.01}
              {...form.getInputProps('percentageVal')}
              placeholder="2.5"
            />
          </Field>
        </>
      )}

      {watchedPriceType === 'formula' && (
        <>
          <Field
            label={t('tiers.form.coefficient', 'Koeffizient')}
            hint={t('tiers.form.coefficientHint', 'z. B. 0.70, um 70 % der Beiträge anderer Stufen abzuziehen')}
          >
            <TextInput
              type="number"
              min={0}
              max={1}
              step={0.01}
              {...form.getInputProps('coefficient')}
              placeholder="0.70"
            />
          </Field>
          <Field
            label={t('tiers.form.roundTo', 'Runden auf')}
            hint={t('tiers.form.roundHint', 'Aufrunden auf (z. B. 5 → nächste 5 CHF)')}
          >
            <TextInput
              type="number"
              min={1}
              {...form.getInputProps('roundTo')}
              placeholder="5"
            />
          </Field>
          <Field
            label={t('tiers.form.deduct', 'Beiträge abziehen von')}
            hint={t('tiers.form.deductHint', 'Stufen, deren Beiträge in der Formel abgezogen werden')}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                padding: '4px 0',
              }}
            >
              {allTiers
                .filter((ot) => ot.id !== (editTarget?.id ?? '-1'))
                .map((ot) => (
                  <label
                    key={ot.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 'var(--mantine-font-size-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={watchedDeductIds.includes(Number(ot.id))}
                      onChange={(e) => {
                        const id = Number(ot.id)
                        form.setFieldValue(
                          'deductIds',
                          e.target.checked
                            ? [...watchedDeductIds, id]
                            : watchedDeductIds.filter((v: number) => v !== id),
                        )
                      }}
                    />
                    <span style={{ color: ot.color }}>?</span>
                    {ot.name}
                  </label>
                ))}
              {allTiers.filter((ot) => ot.id !== (editTarget?.id ?? '-1'))
                .length === 0 && (
                <span
                  style={{
                    color: '#8c86a0',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                >
                  {t('tiers.form.noOtherTiers', 'Keine anderen Stufen vorhanden')}
                </span>
              )}
            </div>
          </Field>
        </>
      )}

      {costPreview && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 8,
            background: '#f7f6fb',
            fontSize: 'var(--mantine-font-size-sm)',
            fontWeight: 600,
            color: '#1a1625',
          }}
        >
          {costSummary(t, costPreview)}
          {costPreview.members > 1 && (
            <span style={{ fontWeight: 400, color: '#5e5873', marginLeft: 8 }}>
              · {t('tiers.memberCount', '{{count}} Mitglieder', { count: costPreview.members })}
            </span>
          )}
        </div>
      )}
    </div>
  )

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('tiers.new', 'Neue Stufe')}
          </Button>
        </Group>
      )}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 14,
        }}
      >
        {tiers.map((tier) => (
          <Paper
            key={tier.id}
            withBorder
            style={{ overflow: 'hidden' }}
          >
            <div style={{ height: 4, background: tier.color }} />
            <div style={{ padding: '20px 22px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 9,
                    background: tier.color + '22',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 'var(--mantine-font-size-md)',
                    fontWeight: 700,
                    color: tier.color,
                  }}
                >
                  {tier.name[0]}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-md)',
                    fontWeight: 700,
                    color: '#1a1625',
                  }}
                >
                  {tier.name}
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 16,
                }}
              >
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#5e5873',
                  }}
                >
                  {t('tiers.price', 'Preis')}
                </span>
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 700,
                    color: '#1a1625',
                  }}
                >
                  {costSummary(t, tierCosts[tier.id]) ??
                    (tier.priceType === 'formula'
                      ? t('tiers.type.formula', 'Formel')
                      : tier.priceType === 'percentage'
                        ? `${tier.percentageValue ?? '?'}%`
                        : tier.priceChf != null
                          ? `CHF ${tier.priceChf}`
                          : '—')}
                </span>
              </div>
              <div
                style={{
                  display: 'flex',
                  gap: 6,
                  marginBottom: 14,
                  flexWrap: 'wrap',
                }}
              >
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#5e5873',
                    background: '#f7f6fb',
                    borderRadius: 4,
                    padding: '2px 8px',
                  }}
                >
                  {tier.priceType ? t(`tiers.type.${tier.priceType}`, tier.priceType) : t('tiers.noType', 'Kein Typ')}
                </span>
                {tier.billingCycle && (
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#5e5873',
                      background: '#f7f6fb',
                      borderRadius: 4,
                      padding: '2px 8px',
                    }}
                  >
                    {t(`tiers.cycle.${tier.billingCycle}`, tier.billingCycle)}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {canUpdate && (
                  <Button
                    variant="subtle"
                    color="blue"
                    style={{ flex: 1 }}
                    onClick={() => openEdit(tier)}
                  >
                    <IconPencil size={16} />
                    {t('common.edit', 'Bearbeiten')}
                  </Button>
                )}
                <Button
                  variant="subtle"
                  color="acc"
                  onClick={() => setDetailTier(tier)}
                >
                  {t('tiers.members', 'Mitglieder')}
                </Button>
                {canDelete && (
                  <Button
                    variant="subtle"
                    color="red"
                    onClick={() => setDeleteTarget(tier)}
                  >
                    <IconTrash size={16} />
                  </Button>
                )}
              </div>
            </div>
          </Paper>
        ))}
        <Paper
          withBorder
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 28,
            cursor: 'pointer',
            border: '1.5px dashed #d6d2e3',
            background: 'transparent',
            minHeight: 200,
          }}
          onClick={openAdd}
        >
          <IconPlus size={22} style={{ color: '#b7b0c9', marginBottom: 8 }} />
          <span
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              color: '#8c86a0',
            }}
          >
            {t('tiers.new', 'Neue Stufe')}
          </span>
        </Paper>
      </div>

      {detailTier && (
        <TierDetailPanel
          tier={detailTier}
          onClose={() => setDetailTier(null)}
          costSummary={tierCosts[detailTier.id]?.summary}
        />
      )}

      <Modal
        onSubmit={form.onSubmit(saveAdd)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('tiers.newTitle', 'Neue Mitgliedschaftsstufe')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              variant="filled"
              type="submit"
              disabled={saving}
            >
              {t('tiers.create', 'Stufe erstellen')}
            </Button>
          </>
        }
      >
        {tierForm}
      </Modal>
      <Modal
        onSubmit={form.onSubmit(saveEdit)}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('tiers.editTitle', 'Stufe bearbeiten')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              variant="filled"
              type="submit"
              disabled={saving}
            >
              {t('common.saveChanges', 'Änderungen speichern')}
            </Button>
          </>
        }
      >
        {tierForm}
        {editTarget && <PaymentPlansEditor tierId={editTarget.id} />}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('tiers.deleteTitle', 'Stufe «{{name}}» löschen?', { name: deleteTarget?.name ?? '' })}
        body={t('tiers.deleteBody', 'Mitglieder in dieser Stufe müssen einer anderen Stufe zugewiesen werden. Das kann nicht rückgängig gemacht werden.')}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
