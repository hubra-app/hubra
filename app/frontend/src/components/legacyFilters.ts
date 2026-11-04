import i18n from 'i18next'
import type { ReactNode } from 'react'
import type { FilterGroup } from '@hubra/ui'

// The DataTable filter props from before the Filter panel. Plugins built
// against the older SDK still pass them; they show up as panel groups.

/** Old chip filters (plugins still pass these): each chip is a button. */
export interface DataTableFilter {
  label: ReactNode
  value: string
  active: boolean
  onClick: () => void
}

/** Old labelled filter slots (plugins still pass these). */
export interface DataTableFilterSlot {
  label: string
  type: 'select' | 'chips'
  selectValue?: string
  selectOptions?: { value: string; label: string }[]
  onSelectChange?: (value: string) => void
  filters?: DataTableFilter[]
}

/** One group from a row of old chips: the first chip is the "no filter" one. */
function chipsToGroup(key: string, label: string, chips: DataTableFilter[]): FilterGroup {
  const active = chips.find((c) => c.active) ?? chips[0]
  return {
    key,
    label,
    value: active?.value ?? '',
    defaultValue: chips[0]?.value ?? '',
    options: chips.map((c) => ({ value: c.value, label: c.label })),
    onChange: (v) => chips.find((c) => c.value === v)?.onClick(),
  }
}

/** Maps the old `filters` / `filterSlots` props onto the Filter panel. */
export function legacyFilterGroups(
  filters?: DataTableFilter[],
  filterSlots?: DataTableFilterSlot[],
): FilterGroup[] {
  const groups: FilterGroup[] = []
  if (filters?.length) groups.push(chipsToGroup('filter', i18n.t('data.filter', 'Filter'), filters))
  filterSlots?.forEach((slot, i) => {
    if (slot.type === 'chips' && slot.filters?.length) {
      groups.push(chipsToGroup(`slot-${i}`, slot.label, slot.filters))
    } else if (slot.type === 'select') {
      const opts = slot.selectOptions ?? []
      groups.push({
        key: `slot-${i}`,
        label: slot.label,
        value: slot.selectValue ?? opts[0]?.value ?? '',
        defaultValue: opts[0]?.value ?? '',
        kind: 'select',
        options: opts,
        onChange: (v) => slot.onSelectChange?.(v),
      })
    }
  })
  return groups
}
