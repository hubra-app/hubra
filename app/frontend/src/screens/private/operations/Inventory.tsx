import { useState } from 'react'
import { Button, TextInput, Select, Badge, Paper, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconPlus, IconSearch } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  usePagination,
  ConfirmModal,
  ErrorBanner,
  DataTable,
  ActionButtons,
  Seg,
  CardGrid,
  CardItem,
  LoadingSpinner,
  EmptyState,
  Pagination,
} from '@/components/ui'
import type { InventoryItem, InventoryCategory, InventoryStatus } from '@/types'
import {
  listInventory,
  createInventoryItem,
  updateInventoryItem,
  deleteInventoryItem,
  type InventoryItemCreate,
} from '@/api/inventory'
import { qk } from '@/data/keys'
import {
  CATEGORIES,
  CATEGORY_COLORS,
  CATEGORY_ICONS,
  STATUSES,
  STATUS_CONFIG,
} from './inventory/constants'
import { ItemDetailPanel } from './inventory/ItemDetailPanel'
import { ItemFormModal } from './inventory/ItemFormModal'

export function InventoryScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('items.items.create')
  const canUpdate = hasPermission('items.items.update')
  const canDelete = hasPermission('items.items.delete')
  const {
    data: items = [],
    isLoading: loading,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: qk.inventory,
    queryFn: () => listInventory(),
  })
  const [catFilter, setCatFilter] = useState<InventoryCategory | 'All'>('All')
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | 'All'>(
    'All',
  )
  const [search, setSearch] = useState('')
  const [view, setView] = useState<'table' | 'cards'>('cards')

  const [deleteTarget, setDeleteTarget] = useState<InventoryItem | null>(null)
  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null)

  // Form state
  // 'new' opens the form for a new item, an item opens it for that item.
  const [formTarget, setFormTarget] = useState<InventoryItem | 'new' | null>(null)

  const filtered = items.filter((item) => {
    if (catFilter !== 'All' && item.category !== catFilter) return false
    if (statusFilter !== 'All' && item.status !== statusFilter) return false
    if (search && !item.name.toLowerCase().includes(search.toLowerCase()))
      return false
    return true
  })

  const pg = usePagination(filtered, 12)

  const saveItem = async (target: InventoryItem | null, input: InventoryItemCreate) => {
    try {
      if (target) {
        const item = await updateInventoryItem(target.id, input)
        if (detailItem?.id === item.id) setDetailItem(item)
      } else {
        await createInventoryItem(input)
      }
      queryClient.invalidateQueries({ queryKey: qk.inventory })
      setFormTarget(null)
      notify(
        'success',
        target ? t('inventory.item.updated', 'Gegenstand gespeichert') : t('inventory.item.added', 'Gegenstand hinzugefügt'),
        target
          ? t('inventory.item.updatedMsg', '{{name}} wurde gespeichert.', { name: input.name })
          : t('inventory.item.addedMsg', '{{name}} wurde zum Inventar hinzugefügt.', { name: input.name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        target ? t('common.updateFailed', 'Speichern fehlgeschlagen') : t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteInventoryItem(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.inventory })
      if (detailItem?.id === deleteTarget.id) setDetailItem(null)
      notify(
        'info',
        t('inventory.item.removed', 'Gegenstand gelöscht'),
        t('inventory.item.removedMsg', '{{name}} wurde gelöscht.', {
          name: deleteTarget.name,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setDeleteTarget(null)
    }
  }

  const handleInstructionChange = (updated: InventoryItem) => {
    queryClient.invalidateQueries({ queryKey: qk.inventory })
    setDetailItem(updated)
  }

  const currentUserId = currentUser ? Number(currentUser.id) : null
  const currentUserName = currentUser?.name ?? ''

  return (
    <div>
      <PageHead
        title={t('inventory.title', 'Inventar')}
        desc={t('inventory.desc', 'Werkzeuge, Geräte und Material im Blick.')}
        actions={
          canCreate && (
            <Button variant="filled" onClick={() => setFormTarget('new')}>
              <IconPlus size={16} />
              {t('inventory.addItem', 'Gegenstand hinzufügen')}
            </Button>
          )
        }
      />

      {fetchError ? (
        <ErrorBanner
          message={
            fetchError instanceof Error
              ? fetchError.message
              : t(
                  'inventory.failedToLoadInventory',
                  'Inventar konnte nicht geladen werden',
                )
          }
          onRetry={() => refetch()}
        />
      ) : view === 'table' ? (
        <DataTable
          breakpoint="wide"
          columns={[
            {
              key: 'name',
              header: t('common.name', 'Name'),
              render: (item) => (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[item.category] }}
                  />
                  <span style={{ color: CATEGORY_COLORS[item.category] }}>
                    {CATEGORY_ICONS[item.category]}
                  </span>
                  <span style={{ fontWeight: 600, color: '#1a1625' }}>
                    {item.name}
                  </span>
                </div>
              ),
            },
            {
              key: 'category',
              header: t('inventory.category', 'Kategorie'),
              width: 120,
              render: (item) => (
                <Badge
                  variant="light"
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    borderColor: CATEGORY_COLORS[item.category] + '44',
                    color: CATEGORY_COLORS[item.category],
                    background: CATEGORY_COLORS[item.category] + '11',
                  }}
                >
                  {item.category === 'Tool'
                    ? t('inventory.tool', 'Werkzeug')
                    : item.category === 'Item'
                      ? t('inventory.itemLabel', 'Gegenstand')
                      : t('inventory.material', 'Material')}
                </Badge>
              ),
            },
            {
              key: 'status',
              header: t('common.status', 'Status'),
              width: 130,
              render: (item) => {
                const sc = STATUS_CONFIG[item.status]
                return (
                  <Badge
                    variant="light"
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      borderColor: sc.color + '44',
                      color: sc.color,
                      background: sc.color + '11',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                    }}
                  >
                    {sc.icon}
                    {t(`inventory.status_${item.status}`, sc.label)}
                  </Badge>
                )
              },
            },
            {
              key: 'owner',
              header: t('inventory.owner', 'Eigentümer:in'),
              render: (item) => (
                <span
                  style={{
                    color: item.ownerName ? '#2e2940' : '#c2c9d0',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {item.ownerName ?? t('inventory.noOwner', 'Keine Eigentümer:in')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: '',
              render: (item) => (
                <div onClick={(e) => e.stopPropagation()}>
                  <ActionButtons
                    onEdit={canUpdate ? () => setFormTarget(item) : undefined}
                    onDelete={
                      canDelete ? () => setDeleteTarget(item) : undefined
                    }
                  />
                </div>
              ),
            },
          ]}
          data={pg.paged}
          loading={loading}
          emptyMessage={t('inventory.noItemsFound', 'Keine Gegenstände gefunden')}
          onRowClick={(item) => setDetailItem(item)}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('inventory.searchItems', 'Gegenstände suchen …')}
          filters={[
            {
              label: t('inventory.allCategories', 'Alle Kategorien'),
              value: 'cat-all',
              active: catFilter === 'All',
              onClick: () => setCatFilter('All'),
            },
            ...CATEGORIES.map((c) => ({
              label: (
                <>
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[c] }}
                  />
                  {c === 'Tool'
                    ? t('inventory.tool', 'Werkzeug')
                    : c === 'Item'
                      ? t('inventory.itemLabel', 'Gegenstand')
                      : t('inventory.material', 'Material')}
                </>
              ),
              value: `cat-${c}`,
              active: catFilter === c,
              onClick: () => setCatFilter(c),
            })),
          ]}
          toolbar={
            <>
              <Select
                size="sm"
                data={[
                  {
                    value: 'All',
                    label: t('inventory.allStatuses', 'Alle Status'),
                  },
                  ...STATUSES.map((s) => ({
                    value: s,
                    label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
                  })),
                ]}
                value={statusFilter}
                onChange={(v) =>
                  setStatusFilter((v ?? 'All') as InventoryStatus | 'All')
                }
                style={{ width: 140 }}
              />
              <Seg
                options={[
                  { value: 'table', label: '\u2261 ' + t('members.tableView') },
                  { value: 'cards', label: '\u229e ' + t('members.cardsView') },
                ]}
                value={view}
                onChange={(v) => setView(v as 'table' | 'cards')}
              />
            </>
          }
          page={pg.page}
          perPage={pg.perPage}
          total={pg.total}
          totalPages={pg.totalPages}
          onPageChange={pg.goPage}
          onPerPageChange={pg.setPerPage}
          getRowKey={(item) => item.id}
        />
      ) : (
        <Paper withBorder shadow="sm" radius="lg">
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
            <TextInput
              style={{ flex: '1 1 220px' }}
              leftSection={<IconSearch size={16} />}
              size="sm"
              placeholder={t('inventory.searchItems', 'Gegenstände suchen …')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                className={`chip${catFilter === 'All' ? ' on' : ''}`}
                onClick={() => setCatFilter('All')}
              >
                {t('inventory.allCategories', 'Alle Kategorien')}
              </button>
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={`chip${catFilter === c ? ' on' : ''}`}
                  onClick={() => setCatFilter(c)}
                >
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[c] }}
                  />
                  {c === 'Tool'
                    ? t('inventory.tool', 'Werkzeug')
                    : c === 'Item'
                      ? t('inventory.itemLabel', 'Gegenstand')
                      : t('inventory.material', 'Material')}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Select
                size="sm"
                data={[
                  {
                    value: 'All',
                    label: t('inventory.allStatuses', 'Alle Status'),
                  },
                  ...STATUSES.map((s) => ({
                    value: s,
                    label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
                  })),
                ]}
                value={statusFilter}
                onChange={(v) =>
                  setStatusFilter((v ?? 'All') as InventoryStatus | 'All')
                }
                style={{ width: 140 }}
              />
              <Seg
                options={[
                  { value: 'table', label: '\u2261 ' + t('members.tableView') },
                  { value: 'cards', label: '\u229e ' + t('members.cardsView') },
                ]}
                value={view}
                onChange={(v) => setView(v as 'table' | 'cards')}
              />
            </div>
          </div>
          {loading ? (
            <LoadingSpinner compact message={t('common.loading', 'Wird geladen …')} />
          ) : pg.paged.length === 0 ? (
            <EmptyState
              title={t('inventory.noItemsFound', 'Keine Gegenstände gefunden')}
            />
          ) : (
            <>
              <div style={{ padding: 16 }}>
                <CardGrid>
                  {pg.paged.map((item) => {
                    const sc = STATUS_CONFIG[item.status]
                    const cc = CATEGORY_COLORS[item.category]
                    return (
                      <CardItem
                        key={item.id}
                        colorBar={cc}
                        icon={
                          <div
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: 8,
                              background: cc + '22',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: cc,
                            }}
                          >
                            {CATEGORY_ICONS[item.category]}
                          </div>
                        }
                        title={item.name}
                        subtitle={
                          item.ownerName ??
                          t('inventory.noOwner', 'Keine Eigentümer:in')
                        }
                        onClick={() => setDetailItem(item)}
                        footer={
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <Badge
                              variant="light"
                              size="sm"
                              style={{
                                borderColor: sc.color + '44',
                                color: sc.color,
                                background: sc.color + '11',
                              }}
                            >
                              {t(`inventory.status_${item.status}`, sc.label)}
                            </Badge>
                            <div onClick={(e) => e.stopPropagation()}>
                              <ActionButtons
                                onEdit={
                                  canUpdate ? () => setFormTarget(item) : undefined
                                }
                                onDelete={
                                  canDelete
                                    ? () => setDeleteTarget(item)
                                    : undefined
                                }
                              />
                            </div>
                          </div>
                        }
                      >
                        {item.description && (
                          <Text
                            size="sm"
                            c="dimmed"
                            style={{
                              marginBottom: 8,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {item.description}
                          </Text>
                        )}
                      </CardItem>
                    )
                  })}
                </CardGrid>
              </div>
              <Pagination
                page={pg.page}
                perPage={pg.perPage}
                total={pg.total}
                totalPages={pg.totalPages}
                goPage={pg.goPage}
                setPerPage={pg.setPerPage}
              />
            </>
          )}
        </Paper>
      )}

      {detailItem && (
        <ItemDetailPanel
          item={detailItem}
          onClose={() => setDetailItem(null)}
          onEdit={() => {
            setFormTarget(detailItem)
            setDetailItem(null)
          }}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          onInstructionChange={handleInstructionChange}
        />
      )}

      <ItemFormModal
        key={formTarget === 'new' ? 'new' : (formTarget?.id ?? 'closed')}
        open={formTarget !== null}
        item={formTarget === 'new' ? null : formTarget}
        onClose={() => setFormTarget(null)}
        onSubmit={(input) => saveItem(formTarget === 'new' ? null : formTarget, input)}
      />
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('inventory.deleteItemTitle', '«{{name}}» löschen?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'inventory.deleteItemBody',
          'Der Gegenstand und alle Einweisungen dazu werden endgültig gelöscht.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
