import { useState } from 'react'
import { Button, Group, Paper, UnstyledButton } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconPencil, IconTrash } from '@tabler/icons-react'
import { useToast, useAuth, useNav } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { ConfirmModal } from '@/components/ui'
import type { MembershipTier } from '@/types'
import type { TierCostPreview } from '@/api/tiers'
import { listTiers, deleteTier, calculateTierCost } from '@/api/tiers'
import { qk } from '@/data/keys'
import { TierFormModal } from './TierFormModal'
import { costSummary } from './tierCost'
import { FeeAdjustmentsList } from './FeeAdjustmentsList'

/* -- Membership tiers -------------------------- */
export function TiersTab() {
  const { notify } = useToast()
  const { t } = useT()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('tiers.tiers.create')
  const canUpdate = hasPermission('tiers.tiers.update')
  const canDelete = hasPermission('tiers.tiers.delete')
  const { data: tiers = [] } = useQuery({
    queryKey: qk.tiers.all,
    queryFn: () => listTiers(),
  })
  const { go } = useNav()
  // The form: closed (null), a new tier ('new') or one to change.
  const [formTarget, setFormTarget] = useState<MembershipTier | 'new' | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<MembershipTier | null>(null)
  const { data: tierCosts = {} } = useQuery({
    queryKey: qk.tiers.costs(tiers),
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

  const openAdd = () => setFormTarget('new')
  const openEdit = (tier: MembershipTier) => setFormTarget(tier)

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTier(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.tiers.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      notify('info', t('tiers.deleted', 'Stufe gelöscht'), t('tiers.deletedMsg', '{{name}} wurde entfernt.', { name: deleteTarget.name }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

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
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
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
                    background: `color-mix(in srgb, ${tier.color} 13%, transparent)`,
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
                <UnstyledButton
                  onClick={() => go(`/app/members/tiers/${tier.id}`)}
                  style={{
                    fontSize: 'var(--mantine-font-size-md)',
                    fontWeight: 700,
                    color: 'var(--hb-text)',
                  }}
                >
                  {tier.name}
                </UnstyledButton>
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
                    color: 'var(--hb-text-2)',
                  }}
                >
                  {t('tiers.price', 'Preis')}
                </span>
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 700,
                    color: 'var(--hb-text)',
                  }}
                >
                  {costSummary(t, tierCosts[tier.id]) ??
                    (tier.priceType === 'formula'
                      ? t('tiers.type.formula', 'Formel')
                      : tier.priceType === 'percentage'
                        ? `${tier.percentageValue ?? '?'}%`
                        : tier.priceChf != null
                          ? `CHF ${tier.priceChf}`
                          : t('tiers.noPrice', 'Kein Beitrag'))}
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
                {tier.priceType && (
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: 'var(--hb-text-2)',
                      background: 'var(--hb-surface-2)',
                      borderRadius: 4,
                      padding: '2px 8px',
                    }}
                  >
                    {t(`tiers.type.${tier.priceType}`, tier.priceType)}
                  </span>
                )}
                {tier.billingCycle && (
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: 'var(--hb-text-2)',
                      background: 'var(--hb-surface-2)',
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
                    color="acc"
                    leftSection={<IconPencil size={16} />}
                    onClick={() => openEdit(tier)}
                  >
                    {t('common.edit', 'Bearbeiten')}
                  </Button>
                )}
                <Button
                  variant="subtle"
                  color="acc"
                  onClick={() => go(`/app/members/tiers/${tier.id}`)}
                >
                  {t('tiers.members', 'Mitglieder')}
                </Button>
                {canDelete && (
                  <Button
                    variant="subtle"
                    color="red"
                    ml="auto"
                    aria-label={t('common.delete', 'Löschen')}
                    title={t('common.delete', 'Löschen')}
                    onClick={() => setDeleteTarget(tier)}
                  >
                    <IconTrash size={16} />
                  </Button>
                )}
              </div>
            </div>
          </Paper>
        ))}
        {canCreate && (
          <Paper
            component="button"
            type="button"
            withBorder
            style={{
              font: 'inherit',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 28,
              cursor: 'pointer',
              border: '1.5px dashed var(--hb-border)',
              background: 'transparent',
              minHeight: 200,
            }}
            onClick={openAdd}
          >
            <IconPlus size={24} style={{ color: 'var(--hb-text-3)', marginBottom: 8 }} />
            <span
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--hb-text-3)',
              }}
            >
              {t('tiers.new', 'Neue Stufe')}
            </span>
          </Paper>
        )}
      </div>

      <FeeAdjustmentsList />

      {formTarget && (
        <TierFormModal
          key={formTarget === 'new' ? 'new' : formTarget.id}
          target={formTarget}
          onClose={() => setFormTarget(null)}
        />
      )}
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
