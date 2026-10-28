import { useMemo } from 'react'
import i18n from 'i18next'
import {
  Table as MantineTable,
  ScrollArea,
  TextInput,
  Select,
  Badge,
  Accordion,
  ActionIcon,
  Group,
  Stack,
  Paper,
  Text,
  Tabs as MantineTabs,
} from '@mantine/core'
import {
  IconSearch,
  IconCheck,
  IconX,
  IconPencil,
  IconTrash,
  IconInbox,
} from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { LoadingSpinner, EmptyState } from './feedback'
import { Pagination } from './layout'
import { clickableProps } from './hooks'

export interface TabDef {
  id: string
  label: string
  icon?: React.ReactNode
}

export function Tabs({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: TabDef[]
  activeTab: string
  onTabChange: (id: string) => void
}) {
  return (
    <MantineTabs
      value={activeTab}
      onChange={(v) => v && onTabChange(v)}
      mb={24}
      variant="default"
      className="hubra-tabs"
      styles={{
        tab: {
          paddingTop: 12,
          paddingBottom: 12,
          paddingLeft: 14,
          paddingRight: 14,
          fontSize: 'var(--mantine-font-size-sm)',
        },
        list: {
          gap: 4,
        },
      }}
    >
      <MantineTabs.List>
        {tabs.map((t) => (
          <MantineTabs.Tab key={t.id} value={t.id} leftSection={t.icon}>
            {t.label}
          </MantineTabs.Tab>
        ))}
      </MantineTabs.List>
    </MantineTabs>
  )
}

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
        <Accordion
          variant="separated"
          radius="lg"
          multiple
          defaultValue={Object.keys(grouped)}
        >
          {Object.entries(grouped)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([ns, nsEntries]) => (
              <Accordion.Item key={ns} value={ns}>
                <Accordion.Control>
                  <Group gap="sm" justify="space-between">
                    <Text
                      fw={700}
                      fz="md"
                      style={{ textTransform: 'capitalize' }}
                    >
                      {ns}
                    </Text>
                    <Badge variant="light" size="sm">
                      {nsEntries.length}
                    </Badge>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel p={0}>
                  <ScrollArea
                    w="100%"
                    type="hover"
                    className="responsive-scroll-wrap"
                  >
                    <MantineTable
                      className="responsive-table"
                      styles={{ table: { tableLayout: 'fixed' } }}
                    >
                      <MantineTable.Thead>
                        <MantineTable.Tr>
                          <MantineTable.Th
                            style={{ width: keyWidth, whiteSpace: 'nowrap' }}
                          >
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
                          <MantineTable.Th
                            style={{ width: 120, whiteSpace: 'nowrap' }}
                          />
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
                                  if (
                                    isValueClickable(entry) &&
                                    editingKey !== entry.key
                                  )
                                    onEditStart(entry)
                                }}
                                style={{
                                  cursor:
                                    isValueClickable(entry) &&
                                    editingKey !== entry.key
                                      ? 'pointer'
                                      : undefined,
                                }}
                              >
                                {editingKey === entry.key ? (
                                  <Group gap={4} align="center">
                                    <TextInput
                                      type={getInputType?.(entry) ?? 'text'}
                                      value={editValue}
                                      onChange={(e) =>
                                        onEditValueChange(e.target.value)
                                      }
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
                                  data-label={
                                    typeof col.header === 'string'
                                      ? col.header
                                      : col.key
                                  }
                                >
                                  {col.render(entry)}
                                </MantineTable.Td>
                              ))}
                              <MantineTable.Td
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Group gap={4} justify="flex-end" wrap="nowrap">
                                  {editingKey !== entry.key &&
                                    renderActions(entry)}
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

export interface DataColumn<T> {
  key: string
  header: ReactNode
  render: (item: T) => ReactNode
  width?: string | number
  thStyle?: React.CSSProperties
}

export interface DataTableFilter {
  label: ReactNode
  value: string
  active: boolean
  onClick: () => void
}

export interface DataTableFilterSlot {
  label: string
  type: 'select' | 'chips'
  selectValue?: string
  selectOptions?: { value: string; label: string }[]
  onSelectChange?: (value: string) => void
  filters?: DataTableFilter[]
}

export function DataTable<T>({
  columns,
  data,
  loading,
  emptyMessage,
  onRowClick,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  filters,
  filterSlots,
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
}: {
  columns: DataColumn<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: ReactNode
  onRowClick?: (item: T) => void
  searchPlaceholder?: string
  searchValue?: string
  onSearchChange?: (v: string) => void
  filters?: DataTableFilter[]
  filterSlots?: DataTableFilterSlot[]
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
}) {
  const hasSearch = !!onSearchChange
  const hasFlatFilters = filters && filters.length > 0
  const hasFilterSlots = filterSlots && filterSlots.length > 0
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
            {col.header}
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

  return (
    <Paper withBorder shadow="sm" radius="lg">
      {(hasSearch || hasFlatFilters || hasFilterSlots || toolbar) && (
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--mantine-color-gray-3)',
            display: 'flex',
            gap: 10,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {hasSearch && (
            <TextInput
              size="sm"
              style={{ flex: '1 1 220px' }}
              leftSection={<IconSearch size={16} />}
              placeholder={searchPlaceholder ?? i18n.t('common.searchPlaceholder', 'Suchen …')}
              value={searchValue ?? ''}
              onChange={(e) => onSearchChange!(e.target.value)}
            />
          )}
          {hasFlatFilters && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {filters!.map((f) => (
                <button
                  key={f.value}
                  className={`chip${f.active ? ' on' : ''}`}
                  onClick={f.onClick}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
          {hasFilterSlots && (
            <div
              style={{
                display: 'flex',
                gap: 0,
                flexWrap: 'wrap',
                alignItems: 'center',
              }}
            >
              {filterSlots!.map((slot, si) => (
                <div
                  key={si}
                  style={{
                    display: 'flex',
                    gap: 6,
                    alignItems: 'center',
                    paddingLeft: si > 0 ? 12 : 0,
                    marginLeft: si > 0 ? 12 : 0,
                    borderLeft: si > 0 ? '1px solid #e6e3ef' : 'none',
                  }}
                >
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: 'var(--mantine-color-ink-3)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {slot.label}
                  </span>
                  {slot.type === 'select' && (
                    <Select
                      size="xs"
                      data={slot.selectOptions ?? []}
                      value={slot.selectValue}
                      onChange={(v) => slot.onSelectChange?.(v ?? '')}
                      style={{ width: 'auto' }}
                    />
                  )}
                  {slot.type === 'chips' &&
                    slot.filters?.map((f) => (
                      <button
                        key={f.value}
                        className={`chip${f.active ? ' on' : ''}`}
                        onClick={f.onClick}
                      >
                        {f.label}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          )}
          {toolbar && (
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              {toolbar}
            </div>
          )}
        </div>
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
            top
          />
        )}

      {loading ? (
        <LoadingSpinner compact message={i18n.t('common.loading', 'Wird geladen …')} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={<IconInbox size={36} />}
          title={typeof emptyMessage === 'string' ? emptyMessage : i18n.t('data.noData', 'Keine Daten')}
        />
      ) : grouped ? (
        <Accordion
          variant="separated"
          radius="lg"
          multiple
          defaultValue={Object.keys(grouped)}
        >
          {Object.entries(grouped)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([groupKey, items]) => (
              <Accordion.Item key={groupKey} value={groupKey}>
                <Accordion.Control>
                  <Group gap="sm" justify="space-between">
                    <Text
                      fw={700}
                      fz="md"
                      style={{ textTransform: 'capitalize' }}
                    >
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
