import type { useT } from '@/locales/i18n'

type Translate = ReturnType<typeof useT>['t']

export const PAYMENT_METHODS = ['Cash', 'IBAN', 'Card', 'Twint'] as const

/** "Bar", "Bank", … for the API's method values. */
export function methodLabel(t: Translate, method: string): string {
  switch (method) {
    case 'Cash':
      return t('finance.methods.cash', 'Bar')
    case 'IBAN':
      return t('finance.methods.bank', 'Bank')
    case 'Card':
      return t('finance.methods.card', 'Karte')
    case 'Twint':
      return 'TWINT'
    default:
      return method
  }
}

/** "Offen" / "Abgeschlossen" for the API's status values. */
export function statusLabel(t: Translate, status: string): string {
  return status === 'Pending'
    ? t('finance.pending', 'Offen')
    : t('finance.completed', 'Abgeschlossen')
}
