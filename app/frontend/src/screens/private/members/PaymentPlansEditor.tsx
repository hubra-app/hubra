import { useState } from 'react'
import {
  ActionIcon,
  Button,
  Group,
  NumberInput,
  Select,
  Switch,
  Text,
  TextInput,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import {
  createPlan,
  deletePlan,
  listPlans,
  updatePlan,
  type PaymentPlan,
  type PlanInput,
  type PlanInterval,
} from '@/api/paymentPlans'

const INTERVALS: PlanInterval[] = ['yearly', 'half_yearly', 'quarterly', 'monthly']

/** Ways a tier can be paid. Saved one plan at a time, outside the tier form. */
export function PaymentPlansEditor({ tierId }: { tierId: string }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data: plans = [] } = useQuery({
    queryKey: ['payment-plans', tierId],
    queryFn: () => listPlans(tierId),
  })
  const [draft, setDraft] = useState<PlanInput | null>(null)

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn()
      await queryClient.invalidateQueries({ queryKey: ['payment-plans', tierId] })
      await queryClient.invalidateQueries({ queryKey: ['tiers'] })
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    }
  }

  const intervalOptions = INTERVALS.map((i) => ({
    value: i,
    label: t(`tiers.plans.intervals.${i}`, i),
  }))

  return (
    <div style={{ marginTop: 20 }}>
      <Text fw={600} fz="sm">
        {t('tiers.plans.title', 'Zahlungspläne')}
      </Text>
      <Text fz="xs" c="dimmed" mb="xs">
        {t(
          'tiers.plans.hint',
          'Mitglieder können diese Stufe in Raten bezahlen. Ohne Plan wird im Rhythmus der Stufe abgerechnet.',
        )}
      </Text>
      {plans.map((p: PaymentPlan) => (
        <Group key={p.id} gap="xs" wrap="nowrap" mb={6} align="center">
          <TextInput
            style={{ flex: 2 }}
            defaultValue={p.name}
            aria-label={t('tiers.plans.name', 'Name')}
            onBlur={(e) =>
              e.currentTarget.value !== p.name &&
              run(() => updatePlan(p.id, { name: e.currentTarget.value }))
            }
          />
          <Select
            style={{ flex: 1.5 }}
            data={intervalOptions}
            value={p.interval}
            allowDeselect={false}
            onChange={(v) => v && run(() => updatePlan(p.id, { interval: v as PlanInterval }))}
          />
          <NumberInput
            style={{ flex: 1 }}
            defaultValue={p.surcharge_pct}
            suffix=" %"
            min={0}
            max={100}
            aria-label={t('tiers.plans.surcharge', 'Zuschlag')}
            onBlur={(e) => {
              const v = parseFloat(e.currentTarget.value) || 0
              if (v !== p.surcharge_pct) run(() => updatePlan(p.id, { surcharge_pct: v }))
            }}
          />
          <Switch
            checked={p.visible}
            label={t('tiers.plans.visible', 'Mitglieder können wählen')}
            onChange={(e) => run(() => updatePlan(p.id, { visible: e.currentTarget.checked }))}
          />
          <ActionIcon
            variant="subtle"
            color="red"
            aria-label={t('common.delete')}
            onClick={() => run(() => deletePlan(p.id))}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ))}
      {draft ? (
        <Group gap="xs" wrap="nowrap" align="center">
          <TextInput
            style={{ flex: 2 }}
            placeholder={t('tiers.plans.namePlaceholder', 'Vierteljährlich')}
            value={draft.name ?? ''}
            onChange={(e) => setDraft({ ...draft, name: e.currentTarget.value })}
          />
          <Select
            style={{ flex: 1.5 }}
            data={intervalOptions}
            value={draft.interval}
            allowDeselect={false}
            onChange={(v) => setDraft({ ...draft, interval: (v as PlanInterval) ?? 'yearly' })}
          />
          <NumberInput
            style={{ flex: 1 }}
            value={draft.surcharge_pct ?? 0}
            suffix=" %"
            min={0}
            max={100}
            onChange={(v) => setDraft({ ...draft, surcharge_pct: Number(v) || 0 })}
          />
          <Button
            size="xs"
            disabled={!draft.name?.trim()}
            onClick={() =>
              run(async () => {
                await createPlan(tierId, draft)
                setDraft(null)
              })
            }
          >
            {t('common.save')}
          </Button>
        </Group>
      ) : (
        <Button
          variant="subtle"
          size="xs"
          onClick={() => setDraft({ name: '', interval: 'quarterly', surcharge_pct: 0 })}
        >
          <IconPlus size={14} />
          {t('tiers.plans.add', 'Zahlungsplan hinzufügen')}
        </Button>
      )}
    </div>
  )
}
