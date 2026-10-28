import type { ComponentProps } from 'react'
import { Pagination as SharedPagination } from '@hubra/ui'
import { tr } from '@/lang'

export { PageHead, StatGrid, StatTile, Tabs, type TabDef } from '@hubra/ui'

export function Pagination(props: ComponentProps<typeof SharedPagination>) {
  return (
    <SharedPagination
      rangeLabel={(start, end, total) => `${start}–${end} ${tr('von', 'of')} ${total}`}
      {...props}
    />
  )
}
