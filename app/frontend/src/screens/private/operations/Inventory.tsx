import { colorText } from '@hubra/ui'
import { useState } from 'react'
import { Button, Badge, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconPlus } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  usePagination,
  ConfirmModal,
  ErrorBanner,
  DataTable,
  ActionButtons,
  CardItem,
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
import { useItemAccess } from './inventory/access'

export function InventoryScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  // Without the club-wide right, members may still add their own items.
  const canCreateAny = hasPermission('inventory.items.create')
  const canCreate = canCreateAny || hasPermission('inventory.items.create_own')
  const accessTo = useItemAccess()
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
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | 'All'>('All')
  const [search, setSearch] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<InventoryItem | null>(null)
  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null)

  // Form state
  // 'new' opens the form for a new item, an item opens it for that item.
  const [formTarget, setFormTarget] = useState<InventoryItem | 'new' | null>(null)

  const filtered = items.filter((item) => {
    if (catFilter !== 'All' && item.category !== catFilter) return false
    if (statusFilter !== 'All' && item.status !== statusFilter) return false
    if (search && !item.name.toLowerCase().includes(search.toLowerCase())) return false
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
        target
          ? t('inventory.item.updated', 'Gegenstand gespeichert')
          : t('inventory.item.added', 'Gegenstand hinzugefügt'),
        target
          ? t('inventory.item.updatedMsg', '{{name}} wurde gespeichert.', { name: input.name })
          : t('inventory.item.addedMsg', '{{name}} wurde zum Inventar hinzugefügt.', {
              name: input.name,
            }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        target
          ? t('common.updateFailed', 'Speichern fehlgeschlagen')
          : t('common.createFailed', 'Erstellen fehlgeschlagen'),
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
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
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

  // The card view (the default): what it is, who owns it, its state.
  const renderCard = (item: InventoryItem) => {
    const sc = STATUS_CONFIG[item.status]
    const cc = CATEGORY_COLORS[item.category]
    return (
      <CardItem
        colorBar={cc}
        icon={
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: `color-mix(in srgb, ${cc} 13%, transparent)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: colorText(cc),
            }}
          >
            {CATEGORY_ICONS[item.category]}
          </div>
        }
        title={item.name}
        subtitle={item.ownerName ?? t('inventory.noOwner', 'Keine Eigentümer:in')}
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
                borderColor: `color-mix(in srgb, ${sc.color} 27%, transparent)`,
                color: sc.color,
                background: `color-mix(in srgb, ${sc.color} 7%, transparent)`,
              }}
            >
              {t(`inventory.status_${item.status}`, sc.label)}
            </Badge>
            <div onClick={(e) => e.stopPropagation()}>
              <ActionButtons
                onEdit={accessTo(item).canEdit ? () => setFormTarget(item) : undefined}
                onDelete={accessTo(item).canDelete ? () => setDeleteTarget(item) : undefined}
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
  }

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
              : t('inventory.failedToLoadInventory', 'Inventar konnte nicht geladen werden')
          }
          onRetry={() => refetch()}
        />
      ) : (
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
                  <span className="dot" style={{ background: CATEGORY_COLORS[item.category] }} />
                  <span style={{ color: colorText(CATEGORY_COLORS[item.category]) }}>
                    {CATEGORY_ICONS[item.category]}
                  </span>
                  <span style={{ fontWeight: 600, color: 'var(--hb-text)' }}>{item.name}</span>
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
                    borderColor: `color-mix(in srgb, ${CATEGORY_COLORS[item.category]} 27%, transparent)`,
                    color: colorText(CATEGORY_COLORS[item.category]),
                    background: `color-mix(in srgb, ${CATEGORY_COLORS[item.category]} 7%, transparent)`,
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
                      borderColor: `color-mix(in srgb, ${sc.color} 27%, transparent)`,
                      color: sc.color,
                      background: `color-mix(in srgb, ${sc.color} 7%, transparent)`,
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
                    color: item.ownerName ? 'var(--hb-text)' : 'var(--hb-text-3)',
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
                    onEdit={accessTo(item).canEdit ? () => setFormTarget(item) : undefined}
                    onDelete={accessTo(item).canDelete ? () => setDeleteTarget(item) : undefined}
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
          filterGroups={[
            {
              key: 'category',
              label: t('inventory.category', 'Kategorie'),
              value: catFilter,
              defaultValue: 'All',
              options: [
                { value: 'All', label: t('inventory.allCategories', 'Alle Kategorien') },
                ...CATEGORIES.map((c) => {
                  const text =
                    c === 'Tool'
                      ? t('inventory.tool', 'Werkzeug')
                      : c === 'Item'
                        ? t('inventory.itemLabel', 'Gegenstand')
                        : t('inventory.material', 'Material')
                  return {
                    value: c,
                    text,
                    label: (
                      <>
                        <span className="dot" style={{ background: CATEGORY_COLORS[c] }} />
                        {text}
                      </>
                    ),
                  }
                }),
              ],
              onChange: (v) => setCatFilter(v as InventoryCategory | 'All'),
            },
            {
              key: 'status',
              label: t('common.status', 'Status'),
              value: statusFilter,
              defaultValue: 'All',
              options: [
                { value: 'All', label: t('inventory.allStatuses', 'Alle Status') },
                ...STATUSES.map((st) => ({
                  value: st,
                  label: t(`inventory.status_${st}`, STATUS_CONFIG[st].label),
                })),
              ],
              onChange: (v) => setStatusFilter(v as InventoryStatus | 'All'),
            },
          ]}
          renderCard={renderCard}
          viewKey="inventory"
          page={pg.page}
          perPage={pg.perPage}
          total={pg.total}
          totalPages={pg.totalPages}
          onPageChange={pg.goPage}
          onPerPageChange={pg.setPerPage}
          getRowKey={(item) => item.id}
        />
      )}

      {detailItem && (
        <ItemDetailPanel
          item={detailItem}
          onClose={() => setDetailItem(null)}
          access={accessTo(detailItem)}
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
        canHandOn={
          formTarget === 'new' ? canCreateAny : !!formTarget && accessTo(formTarget).canHandOn
        }
        canGiveAway={
          formTarget === 'new' ? canCreateAny : !!formTarget && accessTo(formTarget).canGiveAway
        }
        ownerIfFixed={currentUserId ?? undefined}
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
