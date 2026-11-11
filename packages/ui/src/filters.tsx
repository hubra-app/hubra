import { useState } from 'react'
import {
  Badge,
  Button,
  CloseButton,
  Drawer,
  Group,
  Popover,
  Select,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
  useMatches,
} from '@mantine/core'
import { DateField } from './dates'
import { IconAdjustmentsHorizontal, IconSearch, IconX } from '@tabler/icons-react'
import type { ReactNode } from 'react'

// One toolbar for every list (docs/table-controls.md): a search field, one
// "Filter" button that opens a panel with all filters and the sort order, and
// the active ones as removable chips under it. A filter at its default value
// shows no chip, so an untouched list has a single quiet row.

export interface FilterOption {
  value: string
  label: ReactNode
  /** The chip text when `label` is not a string (e.g. a coloured dot + text). */
  text?: string
}

export interface FilterGroup {
  key: string
  /** The group's heading in the panel, and the chip's prefix. */
  label: string
  value: string
  /** The value that means "no filter"; it shows no chip and "Reset" goes back to it. */
  defaultValue: string
  onChange: (value: string) => void
  options?: FilterOption[]
  /**
   * choice: buttons (a searchable select when there are more than 8 options);
   * select: always a select; date: a date field ('' = none).
   */
  kind?: 'choice' | 'select' | 'date'
  min?: string
  max?: string
  /** Not offered right now (e.g. tiers while the archive is shown). */
  hidden?: boolean
  /** Sort order: listed last in the panel and shown as a chip like a filter. */
  sort?: boolean
}

export interface FilterLabels {
  search: string
  filter: string
  reset: string
  done: string
  remove: (chip: string) => string
}

const DEFAULT_LABELS: FilterLabels = {
  search: 'Suchen …',
  filter: 'Filter',
  reset: 'Zurücksetzen',
  done: 'Fertig',
  remove: (chip) => `${chip} entfernen`,
}

function optionText(group: FilterGroup, value: string): string {
  if (group.kind === 'date') return value
  const opt = group.options?.find((o) => o.value === value)
  if (!opt) return value
  return opt.text ?? (typeof opt.label === 'string' ? opt.label : value)
}

/** Groups that differ from their default, in panel order. */
export function activeFilters(groups: FilterGroup[]) {
  return groups.filter((g) => !g.hidden && g.value !== g.defaultValue)
}

function GroupControl({ group }: { group: FilterGroup }) {
  const options = group.options ?? []
  if (group.kind === 'date') {
    return (
      <DateField
        size="sm"
        aria-label={group.label}
        value={group.value}
        min={group.min}
        max={group.max}
        onChange={(v) => group.onChange(v)}
        // The filter already sits in a popover; a second one in a portal
        // would count as a click outside and close it.
        popoverProps={{ withinPortal: false }}
        rightSection={
          group.value ? (
            <CloseButton size="sm" aria-label={group.label} onClick={() => group.onChange('')} />
          ) : null
        }
      />
    )
  }
  if (group.kind === 'select' || options.length > 8) {
    return (
      <Select
        size="sm"
        aria-label={group.label}
        data={options.map((o) => ({
          value: o.value,
          label: o.text ?? (typeof o.label === 'string' ? o.label : o.value),
        }))}
        value={group.value}
        onChange={(v) => group.onChange(v ?? group.defaultValue)}
        searchable={options.length > 8}
        allowDeselect={false}
        comboboxProps={{ withinPortal: false }}
      />
    )
  }
  return (
    <div
      role="radiogroup"
      aria-label={group.label}
      style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}
    >
      {options.map((o) => {
        const on = o.value === group.value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            className={`chip${on ? ' on' : ''}`}
            onClick={() => group.onChange(o.value)}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

function FilterPanel({
  groups,
  labels,
  onDone,
}: {
  groups: FilterGroup[]
  labels: FilterLabels
  onDone: () => void
}) {
  const shown = [
    ...groups.filter((g) => !g.hidden && !g.sort),
    ...groups.filter((g) => !g.hidden && g.sort),
  ]
  const anyActive = activeFilters(groups).length > 0
  return (
    <Stack gap="md">
      {shown.map((g) => (
        <Stack key={g.key} gap={6}>
          <Text size="xs" fw={600} c="dimmed" tt="uppercase" style={{ letterSpacing: '0.04em' }}>
            {g.label}
          </Text>
          <GroupControl group={g} />
        </Stack>
      ))}
      <Group justify="space-between" gap="xs">
        <Button
          variant="subtle"
          size="xs"
          disabled={!anyActive}
          onClick={() =>
            groups.forEach((g) => g.value !== g.defaultValue && g.onChange(g.defaultValue))
          }
        >
          {labels.reset}
        </Button>
        <Button size="xs" onClick={onDone}>
          {labels.done}
        </Button>
      </Group>
    </Stack>
  )
}

/** The "Filter" button and its panel: a popover on wider screens, a bottom sheet on phones. */
export function FilterButton({
  groups,
  labels: labelOverrides,
}: {
  groups: FilterGroup[]
  labels?: Partial<FilterLabels>
}) {
  const labels = { ...DEFAULT_LABELS, ...labelOverrides }
  const [open, setOpen] = useState(false)
  const phone = useMatches({ base: true, sm: false })
  const count = activeFilters(groups).length
  if (groups.every((g) => g.hidden)) return null

  const button = (
    <Button
      variant={count ? 'light' : 'default'}
      size="sm"
      leftSection={<IconAdjustmentsHorizontal size={16} />}
      rightSection={
        count ? (
          <Badge size="xs" circle variant="filled">
            {count}
          </Badge>
        ) : undefined
      }
      onClick={() => setOpen((o) => !o)}
      aria-expanded={open}
      aria-haspopup="dialog"
    >
      {labels.filter}
    </Button>
  )
  const panel = <FilterPanel groups={groups} labels={labels} onDone={() => setOpen(false)} />

  if (phone) {
    return (
      <>
        {button}
        <Drawer
          opened={open}
          onClose={() => setOpen(false)}
          position="bottom"
          size="auto"
          title={labels.filter}
          // Only as tall as the filters need, so the list stays in view above it.
          styles={{
            content: {
              height: 'auto',
              maxHeight: '85dvh',
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
            },
          }}
        >
          {panel}
        </Drawer>
      </>
    )
  }
  return (
    <Popover
      opened={open}
      onChange={setOpen}
      position="bottom-end"
      width={340}
      shadow="md"
      trapFocus
      withinPortal
    >
      <Popover.Target>{button}</Popover.Target>
      <Popover.Dropdown aria-label={labels.filter} role="dialog">
        {panel}
      </Popover.Dropdown>
    </Popover>
  )
}

/** The active filters as removable chips, plus "Reset" when more than one is set. */
export function ActiveFilterChips({
  groups,
  labels: labelOverrides,
}: {
  groups: FilterGroup[]
  labels?: Partial<FilterLabels>
}) {
  const labels = { ...DEFAULT_LABELS, ...labelOverrides }
  const active = activeFilters(groups)
  if (!active.length) return null
  return (
    <Group gap={6} wrap="wrap">
      {active.map((g) => {
        const text = `${g.label}: ${optionText(g, g.value)}`
        return (
          <span key={g.key} className="chip on filter-chip">
            {text}
            <UnstyledButton
              aria-label={labels.remove(text)}
              title={labels.remove(text)}
              onClick={() => g.onChange(g.defaultValue)}
              style={{ display: 'inline-flex', color: 'inherit' }}
            >
              <IconX size={14} />
            </UnstyledButton>
          </span>
        )
      })}
      {active.length > 1 && (
        <Button
          variant="subtle"
          size="compact-sm"
          onClick={() => active.forEach((g) => g.onChange(g.defaultValue))}
        >
          {labels.reset}
        </Button>
      )}
    </Group>
  )
}

/**
 * Search + Filter button + actions on one row, active filter chips below.
 * Used by DataTable in the club app and directly above manage's tables.
 */
export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder,
  groups = [],
  actions,
  labels,
  padded,
}: {
  search?: string
  onSearchChange?: (v: string) => void
  searchPlaceholder?: string
  groups?: FilterGroup[]
  /** Right-aligned extras: refresh, view switch. */
  actions?: ReactNode
  labels?: Partial<FilterLabels>
  /** Inside a bordered card: padding and a divider below. */
  padded?: boolean
}) {
  const hasGroups = groups.some((g) => !g.hidden)
  if (!onSearchChange && !hasGroups && !actions) return null
  return (
    <div
      className="filter-bar"
      style={
        padded ? { padding: '12px 16px', borderBottom: '1px solid var(--hb-border)' } : undefined
      }
    >
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {onSearchChange && (
          <TextInput
            size="sm"
            style={{ flex: '1 1 140px', maxWidth: 420 }}
            leftSection={<IconSearch size={16} />}
            placeholder={searchPlaceholder ?? labels?.search ?? DEFAULT_LABELS.search}
            aria-label={searchPlaceholder ?? labels?.search ?? DEFAULT_LABELS.search}
            value={search ?? ''}
            onChange={(e) => onSearchChange(e.currentTarget.value)}
            rightSection={
              search ? (
                <CloseButton
                  size="sm"
                  aria-label={labels?.reset ?? DEFAULT_LABELS.reset}
                  onClick={() => onSearchChange('')}
                />
              ) : null
            }
          />
        )}
        {hasGroups && <FilterButton groups={groups} labels={labels} />}
        {actions && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            {actions}
          </div>
        )}
      </div>
      {hasGroups && activeFilters(groups).length > 0 && (
        <div style={{ marginTop: 10 }}>
          <ActiveFilterChips groups={groups} labels={labels} />
        </div>
      )}
    </div>
  )
}
