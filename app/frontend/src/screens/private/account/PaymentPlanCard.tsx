import { useState } from 'react'
import { Group, Paper, Radio, Stack, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconCalendarRepeat } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { formatCHF } from '@/format'
import { chooseMyPlan, getMyPlanOptions } from '@/api/paymentPlans'

/** Lets a member pick how they pay their tier, when the tier offers plans. */
export function PaymentPlanCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({
    queryKey: ['my-plan'],
    queryFn: getMyPlanOptions,
  })
  if (!data?.tier || data.plans.length === 0) return null
  const tier = data.tier

  const choose = async (value: string) => {
    setBusy(true)
    try {
      await chooseMyPlan(value === 'tier' ? null : Number(value))
      await queryClient.invalidateQueries({ queryKey: ['my-plan'] })
      notify('success', t('account.plan.saved', 'Payment plan saved'))
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setBusy(false)
    }
  }

  const per = (interval: string | null) =>
    t(`tiers.plans.per.${interval ?? 'yearly'}`, interval ?? 'yearly')

  return (
    <Paper withBorder shadow="sm" radius="lg" mt="md">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        <IconCalendarRepeat size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.plan.title', 'How you pay')}
        </Text>
      </Group>
      <Radio.Group
        value={data.current_plan_id ? String(data.current_plan_id) : 'tier'}
        onChange={choose}
        p="md"
      >
        <Stack gap="sm">
          <Radio
            value="tier"
            disabled={busy}
            label={`${t('account.plan.standard', 'Standard')}: ${formatCHF(tier.amount)} ${per(tier.billing_cycle)}`}
          />
          {data.plans.map((p) => (
            <Radio
              key={p.id}
              value={String(p.id)}
              disabled={busy}
              label={`${p.name}: ${formatCHF(p.amount ?? 0)} ${per(p.interval)}`}
            />
          ))}
        </Stack>
      </Radio.Group>
      <Text fz="xs" c="dimmed" px="md" pb="md">
        {t(
          'account.plan.hint',
          'Applies from your next invoice. Invoices already sent stay as they are.',
        )}
      </Text>
    </Paper>
  )
}
