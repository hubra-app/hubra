import { formatCHF } from '@/format'
import type { useT } from '@/locales/i18n'
import type { FeeAdjustment } from '@/api/feeAdjustments'

type T = ReturnType<typeof useT>['t']

/** "Befreit", "CHF 60.00 pro Jahr", "50 % weniger". */
export function feeAdjustmentLabel(adj: FeeAdjustment, t: T): string {
  if (adj.kind === 'exempt') return t('fees.kind.exemptShort', 'Vom Beitrag befreit')
  if (adj.kind === 'amount')
    return t('fees.kind.amountShort', 'CHF {{amount}} pro Jahr', {
      amount: formatCHF(adj.amount_chf ?? 0),
    })
  return t('fees.kind.percentShort', '{{percent}} % weniger', { percent: adj.percent ?? 0 })
}

