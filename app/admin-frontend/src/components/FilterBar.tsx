import { FilterBar as SharedFilterBar } from '@hubra/ui'
import type { ComponentProps } from 'react'
import { useLang } from '@/lang'

/** Search + one "Filter" button + active filter chips, in manage's language. */
export function FilterBar(props: Omit<ComponentProps<typeof SharedFilterBar>, 'labels'>) {
  const { tr } = useLang()
  return (
    <SharedFilterBar
      labels={{
        search: tr('Suchen …', 'Search…'),
        filter: tr('Filter', 'Filter'),
        reset: tr('Zurücksetzen', 'Reset'),
        done: tr('Fertig', 'Done'),
        remove: (chip) => tr(`${chip} entfernen`, `Remove ${chip}`),
      }}
      {...props}
    />
  )
}
