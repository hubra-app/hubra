import { useEffect, useState } from 'react'
import { Button, Checkbox, MultiSelect, Select, SimpleGrid, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/context/AppContext'
import { lookupsQuery } from '@/api/lookups'
import { useT } from '@/locales/i18n'
import { Field, Modal } from '@/components/ui'
import type { MembershipTier } from '@/types'
import { calculateTierCost, createTier, listTiers, updateTier, type TierCostPreview } from '@/api/tiers'
import { qk } from '@/data/keys'
import { PaymentPlansEditor } from './PaymentPlansEditor'
import { costSummary } from './tierCost'

type Translate = ReturnType<typeof useT>['t']

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
  groupIds: z.array(z.string()),
})
type TierForm = z.infer<ReturnType<typeof makeTierSchema>>

function tierBody(data: TierForm) {
  return {
    name: data.name,
    color: data.color,
    priceChf: data.price ? Number(data.price) : null,
    billingCycle: (data.billingCycle || null) as 'monthly' | 'yearly' | null,
    priceType: data.priceType,
    percentageValue: data.percentageVal ? Number(data.percentageVal) : null,
    coefficient: data.coefficient ? Number(data.coefficient) : null,
    roundTo: data.roundTo ? Number(data.roundTo) : null,
    deductTierIds: data.deductIds,
    groupIds: data.groupIds.map(Number),
  }
}

/** Create a tier ('new') or change one, from the list or the tier's page.
 * Mount it with a `key` per target so the form starts from that tier. */
export function TierFormModal({
  target,
  onClose,
}: {
  target: MembershipTier | 'new' | null
  onClose: () => void
}) {
  const { notify } = useToast()
  const { t } = useT()
  const queryClient = useQueryClient()
  const editTarget = target && target !== 'new' ? target : null
  const [saving, setSaving] = useState(false)
  const { data: allTiers = [] } = useQuery({ queryKey: qk.tiers.all, queryFn: () => listTiers() })

  const form = useForm<TierForm>({
    validate: zod4Resolver(makeTierSchema(t)),
    initialValues: editTarget
      ? {
          name: editTarget.name,
          color: editTarget.color,
          priceType: editTarget.priceType,
          billingCycle: editTarget.billingCycle ?? '',
          price: editTarget.priceChf != null ? String(editTarget.priceChf) : '',
          percentageVal: editTarget.percentageValue != null ? String(editTarget.percentageValue) : '',
          coefficient: editTarget.coefficient != null ? String(editTarget.coefficient) : '',
          roundTo: editTarget.roundTo != null ? String(editTarget.roundTo) : '',
          deductIds: editTarget.deductTierIds ?? [],
          groupIds: (editTarget.groupIds ?? []).map(String),
        }
      : {
          name: '',
          color: '#7441e0',
          priceType: 'fixed',
          billingCycle: '',
          price: '',
          percentageVal: '',
          coefficient: '',
          roundTo: '',
          deductIds: [],
          groupIds: [],
        },
  })
  const { data: lookups } = useQuery(lookupsQuery)
  const groupOptions = lookups
    ? [...lookups.groups.entries()].map(([id, g]) => ({ value: String(id), label: g.name }))
    : []

  const watchedPriceType = form.values.priceType
  const watchedBillingCycle = form.values.billingCycle
  const watchedPrice = form.values.price
  const watchedPercentageVal = form.values.percentageVal
  const watchedCoefficient = form.values.coefficient
  const watchedRoundTo = form.values.roundTo
  const watchedDeductIds = form.values.deductIds
  const editId = editTarget?.id

  const [costPreview, setCostPreview] = useState<TierCostPreview | null>(null)
  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const result = await calculateTierCost({
          priceType: watchedPriceType,
          billingCycle: (watchedBillingCycle || null) as 'monthly' | 'yearly' | null,
          priceChf: watchedPrice ? Number(watchedPrice) : null,
          percentageValue: watchedPercentageVal ? Number(watchedPercentageVal) : null,
          coefficient: watchedCoefficient ? Number(watchedCoefficient) : null,
          roundTo: watchedRoundTo ? Number(watchedRoundTo) : null,
          deductTierIds: watchedDeductIds,
          tierId: editId ? Number(editId) : undefined,
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
    editId,
  ])

  const save = async (data: TierForm) => {
    setSaving(true)
    try {
      if (editTarget) {
        await updateTier(editTarget.id, tierBody(data))
        notify('success', t('tiers.updated', 'Stufe aktualisiert'), t('tiers.updatedMsg', '{{name}} wurde gespeichert.', { name: data.name }))
      } else {
        await createTier(tierBody(data))
        notify(
          'success',
          t('tiers.created', 'Stufe erstellt'),
          t('tiers.createdMsg', 'Die Stufe {{name}} ist aktiv.', { name: data.name }),
        )
      }
      queryClient.invalidateQueries({ queryKey: qk.tiers.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      onClose()
    } catch (err: unknown) {
      notify(
        'error',
        editTarget
          ? t('common.updateFailed', 'Aktualisieren fehlgeschlagen')
          : t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  const otherTiers = allTiers.filter((ot) => ot.id !== (editTarget?.id ?? '-1'))

  return (
    <Modal
      onSubmit={form.onSubmit(save)}
      open={target != null}
      onClose={onClose}
      wide
      title={editTarget ? t('tiers.editTitle', 'Stufe bearbeiten') : t('tiers.newTitle', 'Neue Mitgliedschaftsstufe')}
      subtitle={editTarget?.name}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" type="submit" disabled={saving}>
            {editTarget ? t('common.saveChanges', 'Änderungen speichern') : t('tiers.create', 'Stufe erstellen')}
          </Button>
        </>
      }
    >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 72px', gap: 12 }}>
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
              </>
            )}
          </SimpleGrid>

          {watchedPriceType === 'formula' && (
            <Field
              label={t('tiers.form.deduct', 'Beiträge abziehen von')}
              hint={t('tiers.form.deductHint', 'Stufen, deren Beiträge in der Formel abgezogen werden')}
            >
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={6} py={4}>
                {otherTiers.map((ot) => (
                  <Checkbox
                    key={ot.id}
                    size="sm"
                    checked={watchedDeductIds.includes(Number(ot.id))}
                    onChange={(e) => {
                      const id = Number(ot.id)
                      form.setFieldValue(
                        'deductIds',
                        e.currentTarget.checked
                          ? [...watchedDeductIds, id]
                          : watchedDeductIds.filter((v: number) => v !== id),
                      )
                    }}
                    label={
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span
                          aria-hidden
                          style={{ width: 8, height: 8, borderRadius: 4, background: ot.color }}
                        />
                        {ot.name}
                      </span>
                    }
                  />
                ))}
                {otherTiers.length === 0 && (
                  <span
                    style={{
                      color: 'var(--hb-text-3)',
                      fontSize: 'var(--mantine-font-size-xs)',
                    }}
                  >
                    {t('tiers.form.noOtherTiers', 'Keine anderen Stufen vorhanden')}
                  </span>
                )}
              </SimpleGrid>
            </Field>
          )}

          {groupOptions.length > 0 && (
            <Field
              label={t('tiers.form.groups', 'Mitglieder kommen in die Gruppen')}
              hint={t(
                'tiers.form.groupsHint',
                'Wer diese Stufe hat, ist in diesen Gruppen. Bei einem Stufenwechsel wechseln auch die Gruppen.',
              )}
            >
              <MultiSelect
                data={groupOptions}
                value={form.values.groupIds}
                onChange={(v) => form.setFieldValue('groupIds', v)}
                placeholder={form.values.groupIds.length ? undefined : t('tiers.form.noGroups', 'Keine Gruppe')}
                clearable
                searchable
                data-testid="tier-groups"
              />
            </Field>
          )}

          {costPreview && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: 'var(--hb-surface-2)',
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                color: 'var(--hb-text)',
              }}
            >
              {costSummary(t, costPreview)}
              {costPreview.members > 1 && (
                <span style={{ fontWeight: 400, color: 'var(--hb-text-2)', marginLeft: 8 }}>
                  · {t('tiers.memberCount', '{{count}} Mitglieder', { count: costPreview.members })}
                </span>
              )}
            </div>
          )}
        </div>
      {editTarget && <PaymentPlansEditor tierId={editTarget.id} />}
    </Modal>
  )
}
