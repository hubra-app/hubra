import { Box } from '@mantine/core'
import {
  FilterBar as SharedFilterBar,
  LoadingState,
  PageTabs,
  Pager,
  SidePanel,
  StatTile as SharedStatTile,
  type FilterGroup,
  type Tone,
} from '@bitsandbricks/ui'
import type { ComponentProps, ReactNode } from 'react'

// Hubra's screens and its plugins (built and published on their own) use
// these components with the props they have always had. They are now the
// shared @bitsandbricks/ui components; only the prop names are adapted
// here, and the words come from the shared texts (useT) in the app's
// language. New code uses @bitsandbricks/ui directly.

export interface TabDef {
  id: string
  label: string
  icon?: ReactNode
}

/** A page's tabs (PageTabs) with Hubra's prop names. */
export function Tabs({
  tabs,
  activeTab,
  onTabChange,
  label,
  mb = 24,
}: {
  tabs: TabDef[]
  activeTab: string
  onTabChange: (id: string) => void
  /** Screen-reader name of the tab row; needed when a page has two. */
  label?: string
  mb?: number
}) {
  return (
    <Box mb={mb}>
      <PageTabs tabs={tabs} active={activeTab} onChange={onTabChange} label={label} />
    </Box>
  )
}

/** The parts of one page tab, as small pills under it (PageTabs `sub`). */
export function SubTabs({
  tabs,
  activeTab,
  onTabChange,
  label,
}: {
  tabs: TabDef[]
  activeTab: string
  onTabChange: (id: string) => void
  /** Screen-reader name of the row, such as "Buchungen". */
  label: string
}) {
  return (
    <Box mb={20}>
      <PageTabs tabs={tabs} active={activeTab} onChange={onTabChange} label={label} sub />
    </Box>
  )
}

const PER_PAGE_OPTS = [10, 25, 50, 100]

/** The shared pager with Hubra's prop names (goPage, setPerPage). */
export function Pagination({
  page,
  perPage,
  total,
  goPage,
  setPerPage,
  top,
  rangeLabel,
}: {
  page: number
  perPage: number
  total: number
  /** Worked out by the pager now; kept so existing callers still type-check. */
  totalPages?: number
  goPage: (p: number) => void
  setPerPage: (n: number) => void
  top?: boolean
  rangeLabel?: (start: number, end: number, total: number) => ReactNode
}) {
  return (
    <Pager
      page={page}
      perPage={perPage}
      total={total}
      onPage={goPage}
      onPerPage={setPerPage}
      // A screen may page by another size (cards in rows of 3 use 12).
      perPageOptions={[...new Set([...PER_PAGE_OPTS, perPage])].sort((a, b) => a - b)}
      rangeLabel={rangeLabel}
      top={top}
    />
  )
}

// Hubra passed a colour for the figure; the shared tile takes a tone.
const ACCENT_TONE: [RegExp, Tone][] = [
  [/red|err/, 'err'],
  [/orange|warn/, 'warn'],
  [/green|ok\b/, 'ok'],
]

/** One figure (the shared StatTile), with Hubra's `accent` colour as a tone. */
export function StatTile({
  label,
  value,
  sub,
  accent,
  icon,
  onClick,
}: {
  label: string
  value: string | number
  sub?: string
  /** The figure's colour; status colours become the matching tone. */
  accent?: string
  icon?: ReactNode
  onClick?: () => void
}) {
  const tone = accent ? ACCENT_TONE.find(([re]) => re.test(accent))?.[1] : undefined
  return <SharedStatTile label={label} value={value} sub={sub} tone={tone} icon={icon} onClick={onClick} />
}

/** The shared side panel under Hubra's name. */
export function SlideOver(
  props: Omit<ComponentProps<typeof SidePanel>, 'href' | 'openLabel' | 'eyebrow'> & {
    /** The close button's name now comes from the shared texts. */
    closeLabel?: string
  },
) {
  const { closeLabel: _closeLabel, ...rest } = props
  return <SidePanel {...rest} />
}

/** Loading: the shared state, with Hubra's name. */
export function LoadingSpinner({ message, compact }: { message?: string; compact?: boolean }) {
  return <LoadingState message={message} compact={compact} />
}

/** The shared filter bar, with Hubra's `searchPlaceholder` prop. */
export function FilterBar({
  searchPlaceholder,
  ...props
}: Omit<ComponentProps<typeof SharedFilterBar>, 'searchLabel'> & {
  searchPlaceholder?: string
}) {
  // Hubra's look: one Filter button with a panel, not a menu per filter.
  return <SharedFilterBar layout="panel" searchLabel={searchPlaceholder} {...props} />
}

export type { FilterGroup }
