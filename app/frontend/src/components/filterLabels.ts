import i18n from 'i18next'
import type { FilterLabels } from '@hubra/ui'

/** The filter panel's texts in the user's language. */
export function filterLabels(): Partial<FilterLabels> {
  return {
    search: i18n.t('common.searchPlaceholder', 'Suchen …'),
    filter: i18n.t('data.filter', 'Filter'),
    reset: i18n.t('data.filterReset', 'Zurücksetzen'),
    done: i18n.t('data.filterDone', 'Fertig'),
    remove: (chip) => i18n.t('data.filterRemove', '{{chip}} entfernen', { chip }),
  }
}
