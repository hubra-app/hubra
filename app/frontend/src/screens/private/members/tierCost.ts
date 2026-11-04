import type { useT } from '@/locales/i18n'
import type { TierCostPreview } from '@/api/tiers'

type Translate = ReturnType<typeof useT>['t']

/** Builds the price line locally so the billing period is translated. */
export function costSummary(
  t: Translate,
  cost: Pick<TierCostPreview, 'amount' | 'period'> | undefined,
): string | undefined {
  if (!cost) return undefined
  if (!(cost.amount > 0)) return '—'
  const period = t(`tiers.per.${cost.period ?? 'period'}`, cost.period ?? 'Periode')
  return `CHF ${cost.amount.toFixed(2)} / ${period}`
}
