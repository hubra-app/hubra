import { useMemo, useState } from 'react'
import i18n from 'i18next'
import {
  Table as MantineTable,
  ScrollArea,
  TextInput,
  Badge,
  Accordion,
  ActionIcon,
  Group,
  Stack,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Text,
  UnstyledButton,
} from '@mantine/core'
import {
  IconSearch,
  IconCheck,
  IconX,
  IconPencil,
  IconTrash,
  IconInbox,
  IconLayoutGrid,
  IconList,
  IconChevronUp,
  IconChevronDown,
  IconSelector,
} from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { FilterBar, type FilterGroup } from '@hubra/ui'
import { filterLabels } from './filterLabels'
import { LoadingSpinner, EmptyState } from './feedback'
import { Pagination } from './layout'
import { clickableProps } from './hooks'

export { Tabs, type TabDef } from '@hubra/ui'

/* ── Table<T> ──────────────────────────────── */

export interface TableColumn<T> {
  key: string
  header: ReactNode
  render: (item: T) => ReactNode
  style?: React.CSSProperties
  thStyle?: React.CSSProperties
}

/* ── KVTable<T> ────────────────────────────── */

export function KVTable<T extends { key: string }>({
  entries,
  loading,
  getNamespace,
  search,
  onSearchChange,
  searchPlaceholder = i18n.t('data.filterKeyValue', 'Nach Schlüssel oder Wert filtern …'),
  extraFilters,
  toolbar,
  editingKey,
  editValue,
  onEditValueChange,
  onEditStart,
  onEditSave,
  onEditCancel,
  saving,
  renderKeyPrefix,
  renderKeySuffix,
  renderKeyBelow,
  renderValue,
  isValueClickable = () => true,
  extraColumns,
  renderActions,
  emptyMessage = i18n.t('data.nothingHere', 'Hier ist noch nichts.'),
  loadingMessage = i18n.t('common.loading', 'Wird geladen …'),
  keyWidth = '36%',
  getInputType,
}: {
  entries: T[]
  loading?: boolean
  getNamespace: (entry: T) => string
  search: string
  onSearchChange: (q: string) => void
  searchPlaceholder?: string
  extraFilters?: ReactNode
  toolbar?: ReactNode
  editingKey: string | null
  editValue: string
  onEditValueChange: (v: string) => void
  onEditStart: (entry: T) => void
  onEditSave: (entry: T) => Promise<void>
  onEditCancel: () => void
  saving?: boolean
  renderKeyPrefix?: (entry: T) => ReactNode
  renderKeySuffix?: (entry: T) => ReactNode
  renderKeyBelow?: (entry: T) => ReactNode
  renderValue: (entry: T) => ReactNode
  isValueClickable?: (entry: T) => boolean
  extraColumns?: Array<{
    key: string
    header: ReactNode
    width?: string | number
    render: (entry: T) => ReactNode
  }>
  renderActions: (entry: T) => ReactNode
  emptyMessage?: string
  loadingMessage?: string
  keyWidth?: string
  getInputType?: (entry: T) => string
}) {
  const grouped = useMemo(() => {
    const g: Record<string, T[]> = {}
    for (const e of entries) {
      const ns = getNamespace(e)
      if (!g[ns]) g[ns] = []
      g[ns].push(e)
    }
    return g
  }, [entries, getNamespace])

  return (
    <Stack gap="md">
      <Group gap="sm" wrap="wrap" align="center">
        <TextInput
          leftSection={<IconSearch size={14} />}
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{ flex: 1, minWidth: 200, maxWidth: 400 }}
        />
        {extraFilters && <Group gap="xs">{extraFilters}</Group>}
        {toolbar && (
          <Group gap="xs" wrap="wrap">
            {toolbar}
          </Group>
        )}
      </Group>

      {loading ? (
        <Text c="dimmed" size="sm" py="lg">
          {loadingMessage}
        </Text>
      ) : Object.keys(grouped).length === 0 ? (
        <Text c="dimmed" size="sm" py="lg">
          {emptyMessage}
        </Text>
      ) : (
        <Accordion variant="separated" radius="lg" multiple defaultValue={Object.keys(grouped)}>
          {Object.entries(grouped)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([ns, nsEntries]) => (
              <Accordion.Item key={ns} value={ns}>
                <Accordion.Control>
                  <Group gap="sm" justify="space-between">
                    <Text fw={700} fz="md" style={{ textTransform: 'capitalize' }}>
                      {ns}
                    </Text>
                    <Badge variant="light" size="sm">
                      {nsEntries.length}
                    </Badge>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel p={0}>
                  <ScrollArea w="100%" type="hover" className="responsive-scroll-wrap">
                    <MantineTable
                      className="responsive-table"
                      styles={{ table: { tableLayout: 'fixed' } }}
                    >
                      <MantineTable.Thead>
                        <MantineTable.Tr>
                          <MantineTable.Th style={{ width: keyWidth, whiteSpace: 'nowrap' }}>
                            {i18n.t('data.key', 'Schlüssel')}
                          </MantineTable.Th>
                          <MantineTable.Th>{i18n.t('data.value', 'Wert')}</MantineTable.Th>
                          {extraColumns?.map((col) => (
                            <MantineTable.Th
                              key={col.key}
                              style={
                                col.width
                                  ? { width: col.width, whiteSpace: 'nowrap' }
                                  : { whiteSpace: 'nowrap' }
                              }
                            >
                              {col.header}
                            </MantineTable.Th>
                          ))}
                          <MantineTable.Th style={{ width: 120, whiteSpace: 'nowrap' }} />
                        </MantineTable.Tr>
                      </MantineTable.Thead>
                      <MantineTable.Tbody>
                        {[...nsEntries]
                          .sort((a, b) => a.key.localeCompare(b.key))
                          .map((entry) => (
                            <MantineTable.Tr key={entry.key}>
                              <MantineTable.Td data-label={i18n.t('data.key', 'Schlüssel')}>
                                <Stack gap={0}>
                                  <Group gap={6} align="center">
                                    {renderKeyPrefix?.(entry)}
                                    <Text className="num" size="sm">
                                      {entry.key}
                                    </Text>
                                    {renderKeySuffix?.(entry)}
                                  </Group>
                                  {renderKeyBelow?.(entry)}
                                </Stack>
                              </MantineTable.Td>
                              <MantineTable.Td
                                data-label={i18n.t('data.value', 'Wert')}
                                onClick={() => {
                                  if (isValueClickable(entry) && editingKey !== entry.key)
                                    onEditStart(entry)
                                }}
                                style={{
                                  cursor:
                                    isValueClickable(entry) && editingKey !== entry.key
                                      ? 'pointer'
                                      : undefined,
                                }}
                              >
                                {editingKey === entry.key ? (
                                  <Group gap={4} align="center">
                                    <TextInput
                                      type={getInputType?.(entry) ?? 'text'}
                                      value={editValue}
                                      onChange={(e) => onEditValueChange(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter') onEditSave(entry)
                                        if (e.key === 'Escape') onEditCancel()
                                      }}
                                      autoFocus
                                      size="xs"
                                      flex={1}
                                    />
                                    <ActionIcon
                                      variant="filled"
                                      color="acc"
                                      size="sm"
                                      onClick={() => onEditSave(entry)}
                                      loading={saving}
                                      aria-label={i18n.t('common.save')}
                                    >
                                      <IconCheck size={12} />
                                    </ActionIcon>
                                    <ActionIcon
                                      variant="subtle"
                                      size="sm"
                                      onClick={onEditCancel}
                                      aria-label={i18n.t('common.cancel')}
                                    >
                                      <IconX size={12} />
                                    </ActionIcon>
                                  </Group>
                                ) : (
                                  renderValue(entry)
                                )}
                              </MantineTable.Td>
                              {extraColumns?.map((col) => (
                                <MantineTable.Td
                                  key={col.key}
                                  data-label={typeof col.header === 'string' ? col.header : col.key}
                                >
                                  {col.render(entry)}
                                </MantineTable.Td>
                              ))}
                              <MantineTable.Td onClick={(e) => e.stopPropagation()}>
                                <Group gap={4} justify="flex-end" wrap="nowrap">
                                  {editingKey !== entry.key && renderActions(entry)}
                                </Group>
                              </MantineTable.Td>
                            </MantineTable.Tr>
                          ))}
                      </MantineTable.Tbody>
                    </MantineTable>
                  </ScrollArea>
                </Accordion.Panel>
              </Accordion.Item>
            ))}
        </Accordion>
      )}
    </Stack>
  )
}

/* ── ActionButtons ──────────────────────────── */

export function ActionButtons({
  onEdit,
  onDelete,
  extra,
  editTitle,
  deleteTitle,
}: {
  onEdit?: () => void
  onDelete?: () => void
  extra?: ReactNode
  editTitle?: string
  deleteTitle?: string
}) {
  return (
    <Group gap={4} wrap="nowrap">
      {extra}
      {onEdit && (
        <ActionIcon
          variant="subtle"
          size="md"
          onClick={onEdit}
          title={editTitle ?? i18n.t('common.edit', 'Bearbeiten')}
        >
          <IconPencil size={18} />
        </ActionIcon>
      )}
      {onDelete && (
        <ActionIcon
          variant="subtle"
          size="md"
          color="red"
          onClick={onDelete}
          title={deleteTitle ?? i18n.t('common.delete', 'Löschen')}
        >
          <IconTrash size={18} />
        </ActionIcon>
      )}
    </Group>
  )
}

/* ── DataTable<T> ────────────────────────────── */

function SortHeader({
  sort,
  value,
  onChange,
  children,
}: {
  sort: { asc: string; desc?: string }
  value: string
  onChange: (v: string) => void
  children: ReactNode
}) {
  const dir = value === sort.asc ? 'asc' : sort.desc !== undefined && value === sort.desc ? 'desc' : null
  const Icon = dir === 'asc' ? IconChevronUp : dir === 'desc' ? IconChevronDown : IconSelector
  const next = dir === 'asc' && sort.desc !== undefined ? sort.desc : sort.asc
  return (
    <UnstyledButton
      onClick={() => onChange(next)}
      aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        font: 'inherit',
        color: 'inherit',
        textTransform: 'inherit',
        letterSpacing: 'inherit',
      }}
    >
      {children}
      <Icon size={14} style={{ opacity: dir ? 1 : 0.4 }} />
    </UnstyledButton>
  )
}

export interface DataColumn<T> {
  key: string
  header: ReactNode
  render: (item: T) => ReactNode
  width?: string | number
  thStyle?: React.CSSProperties
  /** Sortable by its header: the sort values for A→Z and Z→A (desc optional). */
  sort?: { asc: string; desc?: string }
}

export type { FilterGroup } from '@hubra/ui'


type TableView = 'cards' | 'table'

/** The cards / list choice, kept per screen in this browser. */
function useTableView(key: string | undefined, fallback: TableView) {
  const storageKey = key ? `hubra.view.${key}` : null
  const [view, setView] = useState<TableView>(() => {
    try {
      const saved = storageKey ? localStorage.getItem(storageKey) : null
      return saved === 'cards' || saved === 'table' ? saved : fallback
    } catch {
      return fallback
    }
  })
  const choose = (v: TableView) => {
    setView(v)
    try {
      if (storageKey) localStorage.setItem(storageKey, v)
    } catch {
      // private mode: the choice lasts until reload
    }
  }
  return [view, choose] as const
}

export function DataTable<T>({
  columns,
  data,
  loading,
  emptyMessage,
  emptyDescription,
  emptyAction,
  onRowClick,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  filterGroups,
  sortValue,
  onSortChange,
  groupBy,
  page,
  perPage,
  total,
  totalPages,
  onPageChange,
  onPerPageChange,
  toolbar,
  getRowKey,
  breakpoint,
  renderCard,
  viewKey,
  cardsOnly,
}: {
  columns: DataColumn<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: ReactNode
  /** A hint under the empty message, e.g. what to do next. */
  emptyDescription?: string
  /** A button in the empty state, e.g. "Add the first one". */
  emptyAction?: { label: string; onClick: () => void }
  onRowClick?: (item: T) => void
  searchPlaceholder?: string
  searchValue?: string
  onSearchChange?: (v: string) => void
  /** All filters and the sort order, behind one "Filter" button (docs/table-controls.md). */
  filterGroups?: FilterGroup[]
  /** The sort value for columns with `sort`; clicking their header sets it. */
  sortValue?: string
  onSortChange?: (v: string) => void
  groupBy?: {
    getGroup: (item: T) => string
    label?: (group: string) => string
  }
  page?: number
  perPage?: number
  total?: number
  totalPages?: number
  onPageChange?: (p: number) => void
  onPerPageChange?: (n: number) => void
  toolbar?: ReactNode
  getRowKey?: (item: T, index: number) => string | number
  breakpoint?: string
  /** Show the rows as cards, with a cards / list switch in the toolbar. */
  renderCard?: (item: T) => ReactNode
  /** Remembers the chosen view per screen, e.g. "codes". */
  viewKey?: string
  /** Cards only, no list view and no switch: for records a table adds nothing to. */
  cardsOnly?: boolean
}) {
  const [view, setView] = useTableView(viewKey, renderCard ? 'cards' : 'table')
  const showCards = !!renderCard && (cardsOnly || view === 'cards')
  const viewSwitch = renderCard && !cardsOnly ? (
    <SegmentedControl
      size="xs"
      value={view}
      onChange={(v) => setView(v as TableView)}
      data={[
        {
          value: 'cards',
          label: <IconLayoutGrid size={16} aria-label={i18n.t('data.viewCards', 'Karten')} />,
        },
        {
          value: 'table',
          label: <IconList size={16} aria-label={i18n.t('data.viewList', 'Liste')} />,
        },
      ]}
    />
  ) : null

  const hasPagination = page !== undefined && onPageChange !== undefined

  const grouped = useMemo(() => {
    if (!groupBy) return null
    const g: Record<string, T[]> = {}
    for (const item of data) {
      const key = groupBy.getGroup(item)
      if (!g[key]) g[key] = []
      g[key].push(item)
    }
    return g
  }, [data, groupBy])

  const renderTableHeader = () => (
    <MantineTable.Thead>
      <MantineTable.Tr>
        {columns.map((col) => (
          <MantineTable.Th
            key={col.key}
            style={{
              ...(col.width ? { width: col.width } : {}),
              whiteSpace: 'nowrap',
              ...col.thStyle,
            }}
          >
            {col.sort && onSortChange ? (
              <SortHeader
                sort={col.sort}
                value={sortValue ?? ''}
                onChange={onSortChange}
              >
                {col.header}
              </SortHeader>
            ) : (
              col.header
            )}
          </MantineTable.Th>
        ))}
      </MantineTable.Tr>
    </MantineTable.Thead>
  )

  const renderTableRow = (item: T, i: number) => (
    <MantineTable.Tr
      key={getRowKey ? getRowKey(item, i) : i}
      {...clickableProps(onRowClick ? () => onRowClick(item) : undefined)}
      style={{ cursor: onRowClick ? 'pointer' : undefined }}
    >
      {columns.map((col) => {
        const headerText = typeof col.header === 'string' ? col.header : col.key
        return (
          <MantineTable.Td key={col.key} data-label={headerText}>
            {col.render(item)}
          </MantineTable.Td>
        )
      })}
    </MantineTable.Tr>
  )

  const renderTableBody = (items: T[]) => (
    <MantineTable.Tbody>{items.map(renderTableRow)}</MantineTable.Tbody>
  )

  const groups = (filterGroups ?? []).filter(Boolean)
  const actions =
    toolbar || viewSwitch ? (
      <>
        {toolbar}
        {viewSwitch}
      </>
    ) : null

  return (
    <Paper withBorder>
      <FilterBar
        padded
        search={searchValue}
        onSearchChange={onSearchChange}
        searchPlaceholder={searchPlaceholder ?? i18n.t('common.searchPlaceholder', 'Suchen …')}
        groups={groups}
        actions={actions}
        labels={filterLabels()}
      />

      {/* Above the list only when there is more than one page to move through. */}
      {hasPagination &&
        total !== undefined &&
        total > 0 &&
        perPage !== undefined &&
        totalPages !== undefined &&
        totalPages > 1 &&
        onPerPageChange && (
          <Pagination
            page={page!}
            perPage={perPage}
            total={total}
            totalPages={totalPages}
            goPage={onPageChange}
            setPerPage={onPerPageChange}
            top
          />
        )}

      {loading ? (
        <LoadingSpinner compact message={i18n.t('common.loading', 'Wird geladen …')} />
      ) : data.length === 0 ? (
        typeof emptyMessage === 'string' || emptyMessage === undefined ? (
          <EmptyState
            icon={<IconInbox size={36} />}
            title={emptyMessage ?? i18n.t('data.noData', 'Keine Daten')}
            description={emptyDescription}
            action={emptyAction}
          />
        ) : (
          emptyMessage
        )
      ) : showCards ? (
        <SimpleGrid cols={{ base: 1, xs: 2, md: 3, xl: 4 }} spacing="md" p="md">
          {data.map((item, i) => (
            <div key={getRowKey ? getRowKey(item, i) : i}>{renderCard!(item)}</div>
          ))}
        </SimpleGrid>
      ) : grouped ? (
        <Accordion variant="separated" radius="lg" multiple defaultValue={Object.keys(grouped)}>
          {Object.entries(grouped)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([groupKey, items]) => (
              <Accordion.Item key={groupKey} value={groupKey}>
                <Accordion.Control>
                  <Group gap="sm" justify="space-between">
                    <Text fw={700} fz="md" style={{ textTransform: 'capitalize' }}>
                      {groupBy!.label ? groupBy!.label(groupKey) : groupKey}
                    </Text>
                    <Badge variant="light" size="sm">
                      {items.length}
                    </Badge>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel p={0}>
                  <ScrollArea
                    w="100%"
                    type="hover"
                    className="responsive-scroll-wrap"
                    data-breakpoint={breakpoint}
                  >
                    <MantineTable className="responsive-table" highlightOnHover>
                      {renderTableHeader()}
                      {renderTableBody(items)}
                    </MantineTable>
                  </ScrollArea>
                </Accordion.Panel>
              </Accordion.Item>
            ))}
        </Accordion>
      ) : (
        <ScrollArea
          w="100%"
          type="hover"
          className="responsive-scroll-wrap"
          data-breakpoint={breakpoint}
        >
          <MantineTable className="responsive-table" highlightOnHover>
            {renderTableHeader()}
            {renderTableBody(data)}
          </MantineTable>
        </ScrollArea>
      )}

      {hasPagination &&
        total !== undefined &&
        total > 0 &&
        perPage !== undefined &&
        totalPages !== undefined &&
        onPerPageChange && (
          <Pagination
            page={page!}
            perPage={perPage}
            total={total}
            totalPages={totalPages}
            goPage={onPageChange}
            setPerPage={onPerPageChange}
          />
        )}
    </Paper>
  )
}

/* ── SimpleList<T> ───────────────────────────── */

export interface SimpleListRow {
  /** A dot, icon or avatar before the title. */
  leading?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  /** Right-aligned facts: an amount, a date, a badge. */
  meta?: ReactNode
  /** Buttons at the end; clicks on them don't open the row. */
  actions?: ReactNode
  onClick?: () => void
}

/**
 * A plain list for short records (a name and one or two facts), where a
 * table with headers adds nothing (docs/table-controls.md).
 */
export function SimpleList<T>({
  items,
  getKey,
  row,
  loading,
  emptyMessage,
  emptyDescription,
  emptyAction,
  bare,
}: {
  items: T[]
  getKey: (item: T) => string | number
  row: (item: T) => SimpleListRow
  loading?: boolean
  emptyMessage?: string
  emptyDescription?: string
  emptyAction?: { label: string; onClick: () => void }
  /** Inside a card that already has a border. */
  bare?: boolean
}) {
  const body = loading ? (
    <LoadingSpinner compact message={i18n.t('common.loading', 'Wird geladen …')} />
  ) : items.length === 0 ? (
    <EmptyState
      icon={<IconInbox size={36} />}
      title={emptyMessage ?? i18n.t('data.noData', 'Keine Daten')}
      description={emptyDescription}
      action={emptyAction}
    />
  ) : (
    <ul className="simple-list" role="list">
      {items.map((item) => {
        const r = row(item)
        return (
          <li
            key={getKey(item)}
            className={`simple-list-row${r.onClick ? ' clickable' : ''}`}
            {...clickableProps(r.onClick)}
          >
            {r.leading && <div className="simple-list-leading">{r.leading}</div>}
            <div className="simple-list-main">
              <div className="simple-list-title">{r.title}</div>
              {r.subtitle && <div className="simple-list-subtitle">{r.subtitle}</div>}
            </div>
            {r.meta && <div className="simple-list-meta">{r.meta}</div>}
            {r.actions && (
              <div className="simple-list-actions" onClick={(e) => e.stopPropagation()}>
                {r.actions}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
  return bare ? body : <Paper withBorder style={{ overflow: 'hidden' }}>{body}</Paper>
}
