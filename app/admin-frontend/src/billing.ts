import { tr } from '@/lang'
import type { BillingStatus } from '@/api/tenants'

/** Labels and colours for a club's billing status (manage). */
export const STATUS: Record<BillingStatus, { de: string; en: string; color: string }> = {
  none: { de: 'Nicht verrechnet', en: 'Not billed', color: 'gray' },
  trialing: { de: 'Testphase', en: 'Trial', color: 'acc' },
  active: { de: 'Aktiv', en: 'Active', color: 'green' },
  past_due: { de: 'Zahlung überfällig', en: 'Past due', color: 'orange' },
  unpaid: { de: 'Unbezahlt', en: 'Unpaid', color: 'red' },
  canceled: { de: 'Gekündigt', en: 'Canceled', color: 'gray' },
  incomplete: { de: 'Unvollständig', en: 'Incomplete', color: 'orange' },
  paused: { de: 'Pausiert', en: 'Paused', color: 'gray' },
}

export const statusText = (s: BillingStatus) => tr(STATUS[s].de, STATUS[s].en)

export const chf = (amount: string | number | null | undefined) =>
  amount == null || amount === ''
    ? '–'
    : `CHF ${Number(amount).toLocaleString('de-CH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
