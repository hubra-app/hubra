import { useState, useEffect, useMemo } from 'react'
import { Button, Group, Select, Paper, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconPencil, IconTrash } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  Modal,
  Field,
  ConfirmModal,
  MemberSlideOver,
  type SlideOverMember,
} from '@/components/ui'
import type { MembershipTier } from '@/types'
import {
  listTiers,
  createTier,
  updateTier,
  deleteTier,
  calculateTierCost,
} from '@/api/tiers'
import { listTierMembers, listMembers, updateMember } from '@/api/members'
import { PaymentPlansEditor } from './PaymentPlansEditor'

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
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const { data: members = [], isLoading: loading } = useQuery({
    queryKey: ['tier-members', tier.id],
    queryFn: () => listTierMembers(tier.id),
  })
  const { data: searchData } = useQuery({
    queryKey: ['members-search', searchQuery],
    queryFn: () => listMembers({ search: searchQuery, pageSize: 10 }),
    enabled: searchQuery.length >= 2,
  })

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
        notify('success', 'Tier updated', `${m.name} moved to ${tier.name}.`)
        onMemberMoved?.()
      })
      .catch((err: unknown) =>
        notify(
          'error',
          'Update failed',
          err instanceof Error ? err.message : 'Unknown error',
        ),
      )
  }

  return (
    <MemberSlideOver
      title={tier.name}
      subtitle={`${costSummary ?? '—'} · ${tier.billingCycle ?? ''}`}
      icon={
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: 3,
            background: tier.color ?? '#6366f1',
          }}
        />
      }
      members={slideMembers}
      loading={loading}
      addLabel="MOVE MEMBER TO THIS TIER"
      addPlaceholder="Search members…"
      searchResults={searchResults}
      onAdd={handleAdd}
      onAddSearch={setSearchQuery}
      onClose={onClose}
    />
  )
}

/* -- Membership tiers -------------------------- */
const tierSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  color: z.string(),
  priceType: z.enum(['fixed', 'percentage', 'formula']),
  billingCycle: z.string(),
  price: z.string(),
  percentageVal: z.string(),
  coefficient: z.string(),
  roundTo: z.string(),
  deductIds: z.array(z.number()),
})
type TierForm = z.infer<typeof tierSchema>

export function TiersTab() {
  const { notify } = useToast()
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
      const costs: Record<string, { summary: string }> = {}
      await Promise.all(
        tiers.map(async (t) => {
          try {
            costs[t.id] = await calculateTierCost({
              priceType: t.priceType,
              billingCycle: t.billingCycle,
              priceChf: t.priceChf,
              percentageValue: t.percentageValue,
              coefficient: t.coefficient,
              roundTo: t.roundTo,
              deductTierIds: t.deductTierIds,
              tierId: Number(t.id),
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
    validate: zodResolver(tierSchema),
    initialValues: {
      name: '',
      color: '#fece2b',
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

  const [costPreview, setCostPreview] = useState<{
    summary: string
    members: number
  } | null>(null)

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
      color: '#fece2b',
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
  const openEdit = (t: MembershipTier) => {
    setEditTarget(t)
    form.setValues({
      name: t.name,
      color: t.color,
      priceType: t.priceType,
      billingCycle: t.billingCycle ?? '',
      price: t.priceChf != null ? String(t.priceChf) : '',
      percentageVal: t.percentageValue != null ? String(t.percentageValue) : '',
      coefficient: t.coefficient != null ? String(t.coefficient) : '',
      roundTo: t.roundTo != null ? String(t.roundTo) : '',
      deductIds: t.deductTierIds ?? [],
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
        'Tier created',
        `${data.name} membership tier is active.`,
      )
    } catch (err: unknown) {
      notify(
        'error',
        'Create failed',
        err instanceof Error ? err.message : 'Unknown error',
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
      notify('success', 'Tier updated', `${data.name} has been updated.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Update failed',
        err instanceof Error ? err.message : 'Unknown error',
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
      notify('info', 'Tier deleted', `${deleteTarget.name} has been removed.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Delete failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    }
  }

  const allTiers = tiers // local alias for tier select options

  const tierForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 72px', gap: 12 }}
      >
        <Field label="Tier name">
          <TextInput
            {...form.getInputProps('name')}
            placeholder="e.g. Full Access"
          />
        </Field>
        <Field label="Color">
          <TextInput
            type="color"
            {...form.getInputProps('color')}
            style={{ height: 38, padding: '2px 6px', cursor: 'pointer' }}
          />
        </Field>
      </div>

      <Field label="Price type">
        <Select
          data={[
            { value: 'fixed', label: 'Fixed' },
            { value: 'percentage', label: 'Percentage' },
            { value: 'formula', label: 'Formula' },
          ]}
          {...form.getInputProps('priceType')}
        />
      </Field>

      <Field label="Billing cycle">
        <Select
          data={[
            { value: '', label: 'None (manual)' },
            { value: 'monthly', label: 'Monthly' },
            { value: 'yearly', label: 'Yearly' },
          ]}
          {...form.getInputProps('billingCycle')}
        />
      </Field>

      {watchedPriceType === 'fixed' && (
        <Field
          label="Price (CHF)"
          hint={`Per ${watchedBillingCycle || 'period'}`}
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
            label="Percentage value (%)"
            hint="e.g. 2.5 means 2.5% of yearly expenses per member per year"
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
            label="Coefficient"
            hint="e.g. 0.70 to deduct 70% of other tier fees"
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
            label="Round to"
            hint="Round up to nearest (e.g. 5 ? next 5 CHF)"
          >
            <TextInput
              type="number"
              min={1}
              {...form.getInputProps('roundTo')}
              placeholder="5"
            />
          </Field>
          <Field
            label="Deduct tier fees from"
            hint="Select tiers to deduct in formula"
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
                    color: '#99a2ac',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                >
                  No other tiers available
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
            background: '#eef3f0',
            fontSize: 'var(--mantine-font-size-sm)',
            fontWeight: 600,
            color: '#181818',
          }}
        >
          {costPreview.summary}
          {costPreview.members > 1 && (
            <span style={{ fontWeight: 400, color: '#6b7480', marginLeft: 8 }}>
              · {costPreview.members} member
              {costPreview.members !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}
    </div>
  )

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            New tier
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
            shadow="sm"
            radius="lg"
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
                    color: '#181818',
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
                    color: '#6b7480',
                  }}
                >
                  Price
                </span>
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 700,
                    color: '#181818',
                  }}
                >
                  {tierCosts[tier.id]?.summary ??
                    (tier.priceType === 'formula'
                      ? 'Formula'
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
                    color: '#6b7480',
                    background: '#eef3f0',
                    borderRadius: 4,
                    padding: '2px 8px',
                  }}
                >
                  {tier.priceType ?? 'no type'}
                </span>
                {tier.billingCycle && (
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#6b7480',
                      background: '#eef3f0',
                      borderRadius: 4,
                      padding: '2px 8px',
                    }}
                  >
                    {tier.billingCycle}
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
                    Edit
                  </Button>
                )}
                <Button
                  variant="subtle"
                  color="acc"
                  onClick={() => setDetailTier(tier)}
                >
                  Members ?
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
          shadow="sm"
          radius="lg"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 28,
            cursor: 'pointer',
            border: '1.5px dashed #d3ddd7',
            background: 'transparent',
            minHeight: 200,
          }}
          onClick={openAdd}
        >
          <IconPlus size={22} style={{ color: '#b3c1ba', marginBottom: 8 }} />
          <span
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              color: '#99a2ac',
            }}
          >
            New tier
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
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="New membership tier"
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="filled"
              onClick={() => form.onSubmit(saveAdd)()}
              disabled={saving}
            >
              Create tier
            </Button>
          </>
        }
      >
        {tierForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title="Edit tier"
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="filled"
              onClick={() => form.onSubmit(saveEdit)()}
              disabled={saving}
            >
              Save changes
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
        title={`Delete "${deleteTarget?.name}" tier?`}
        body="Members assigned to this tier will need to be reassigned. This cannot be undone."
        onConfirm={confirmDelete}
      />
    </div>
  )
}
