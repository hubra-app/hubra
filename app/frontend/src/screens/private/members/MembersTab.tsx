import { useState, useEffect, useMemo } from 'react'
import { Button, Group, Menu, Select, Paper, Text, TextInput, ActionIcon } from '@mantine/core'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconPlus,
  IconUpload,
  IconPencil,
  IconTrash,
  IconArchive,
  IconUserX,
  IconFileText,
  IconShieldCheckFilled,
  IconDots,
} from '@tabler/icons-react'
import { useNav, useToast, useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import {
  Avatar,
  TierTag,
  StatusBadge,
  Field,
  Modal,
  Tag,
  ConfirmModal,
  DataTable,
  ActionButtons,
  clickableProps,
} from '@/components/ui'
import type { Member } from '@/types'
import {
  listMembers,
  archiveMember,
  unarchiveMember,
  hardDeleteMember,
  exportMembersCSV,
} from '@/api/members'
import { createBulkInvoices } from '@/api/finance'
import { listTiers } from '@/api/tiers'
import { lookupsQuery } from '@/api/lookups'
import { formatCHF } from '@/format'
import { MemberEditModal } from '@/components/MemberEditModal'
import { Invites } from './Invites'
import { useServerPagination } from '@/components/serverPagination'

/* ── Members List ───────────────────────────── */
export function MembersTab() {
  const { t } = useT()
  const { go } = useNav()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const canCreate = hasPermission('members.members.create')
  const canUpdate = hasPermission('members.members.update')
  const canArchive = hasPermission('members.members.archive')
  const canUnarchive = hasPermission('members.members.unarchive')
  const canDelete = hasPermission('members.members.delete')
  const canExport = hasPermission('members.members.export')
  const canBulkInvoice = hasPermission('invoices.invoices.bulk_create')
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [tierFilter, setTierFilter] = useState('All')
  const [showArchived, setShowArchived] = useState(false)
  const [sort, setSort] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Member | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<Member | null>(null)
  const [hardDeleteTarget, setHardDeleteTarget] = useState<Member | null>(null)
  // Bulk invoice state
  const [bulkInvoiceOpen, setBulkInvoiceOpen] = useState(false)
  const [bulkTierId, setBulkTierId] = useState('')
  const [bulkDue, setBulkDue] = useState('')
  const [bulkDescription, setBulkDescription] = useState('')
  const [bulkSaving, setBulkSaving] = useState(false)

  const { data: lookupsData } = useQuery({
    ...lookupsQuery,
  })
  const allTiers = useMemo(
    () =>
      // No made-up tiers while the club's own are still loading.
      lookupsData ? [...lookupsData.tiersByName.keys()] : [],
    [lookupsData],
  )
  const { data: bulkTiers = [] } = useQuery({
    queryKey: qk.tiers.all,
    queryFn: () => listTiers(),
    enabled: bulkInvoiceOpen,
  })

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [search])

  // The API pages the list: ask for the page on screen, not for everything.
  const paging = useServerPagination(`${debouncedSearch}|${tierFilter}|${showArchived}|${sort}`)
  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: qk.members.list(
      debouncedSearch,
      tierFilter,
      showArchived,
      paging.page,
      paging.perPage,
      sort,
    ),
    queryFn: () =>
      listMembers({
        search: debouncedSearch,
        tier: tierFilter,
        archived: showArchived,
        sort: sort || undefined,
        page: paging.page,
        pageSize: paging.perPage,
      }),
    placeholderData: keepPreviousData,
  })
  const members = membersData?.members ?? []
  const pg = paging.withTotal(membersData?.total ?? 0)

  const openBulkInvoice = () => {
    setBulkTierId('')
    setBulkDue('')
    setBulkDescription('')
    setBulkInvoiceOpen(true)
  }

  const handleBulkInvoice = async () => {
    if (!bulkDue) return
    setBulkSaving(true)
    try {
      const result = await createBulkInvoices({
        due: bulkDue,
        tierId: bulkTierId || undefined,
        description: bulkDescription || undefined,
      })
      setBulkInvoiceOpen(false)
      notify(
        'success',
        t('members.bulkInvoice.invoicesCreated', 'Rechnungen erstellt'),
        t('members.bulkInvoice.invoicesCreatedMsg', {
          count: result.created,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('members.bulkInvoice.bulkFailed', 'Sammelrechnung fehlgeschlagen'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setBulkSaving(false)
    }
  }

  const openEdit = (m: Member, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setEditTarget(m)
  }

  const confirmArchive = async () => {
    if (!archiveTarget) return
    try {
      await archiveMember(archiveTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.members.all })
      queryClient.invalidateQueries({ queryKey: qk.dashboard })
      notify(
        'info',
        t('members.archived', 'Mitglied archiviert'),
        `${archiveTarget.name} has been archived.`,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('members.archiveFailed', 'Archivieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleUnarchive = async (m: Member) => {
    try {
      await unarchiveMember(m.id)
      queryClient.invalidateQueries({ queryKey: qk.members.all })
      queryClient.invalidateQueries({ queryKey: qk.dashboard })
      notify(
        'success',
        t('members.member.restoredTitle'),
        t('members.member.restored', { name: m.name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('members.restoreFailed'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const confirmHardDelete = async () => {
    if (!hardDeleteTarget) return
    try {
      await hardDeleteMember(hardDeleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.members.all })
      notify(
        'info',
        t('members.member.deletedTitle', 'Mitglied gelöscht'),
        t('members.member.deletedPermanently', {
          name: hardDeleteTarget.name,
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
    }
  }

  const handleExport = async () => {
    try {
      await exportMembersCSV()
    } catch {
      notify(
        'error',
        t('members.export.failed'),
        t('members.export.failedMsg', 'Die CSV-Datei konnte nicht heruntergeladen werden.'),
      )
    }
  }

  const tiers = ['All', ...allTiers]

  const sortOptions = [
    { value: '', label: t('members.sort.nameAsc', 'Name A–Z') },
    { value: '-name', label: t('members.sort.nameDesc', 'Name Z–A') },
    { value: '-joined', label: t('members.sort.joinedNewest', 'Neueste zuerst') },
    { value: 'joined', label: t('members.sort.joinedOldest', 'Älteste zuerst') },
    { value: 'status', label: t('members.sort.status', 'Status') },
  ]

  // A simple card: who, tier and status, and the actions an admin has.
  const renderMemberCard = (m: Member) => (
    <Paper
      withBorder
      radius="lg"
      p="md"
      h="100%"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        cursor: showArchived ? 'default' : 'pointer',
      }}
      {...clickableProps(showArchived ? undefined : () => go('/app/members/' + m.id, m))}
    >
      <Group gap={12} wrap="nowrap">
        <Avatar name={m.name} color={m.avatarColor} size={44} lastSeen={m.lastSeen} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <Text fw={700} size="sm" truncate>
            {m.name}
          </Text>
          <Text size="xs" c="dimmed" truncate>
            {m.email}
          </Text>
        </div>
      </Group>
      <Group gap={6}>
        <TierTag tier={m.tier} />
        <StatusBadge status={m.status} />
      </Group>
      <Group
        justify="space-between"
        mt="auto"
        pt={8}
        style={{ borderTop: '1px solid var(--hb-border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <Text size="xs" c="dimmed" className="num">
          {m.joined}
        </Text>
        <Group gap={2}>
          {showArchived ? (
            <>
              {canUnarchive && (
                <ActionIcon
                  variant="subtle"
                  onClick={() => handleUnarchive(m)}
                  title={t('members.restore')}
                  aria-label={t('members.restore')}
                >
                  <IconArchive size={18} />
                </ActionIcon>
              )}
              {canDelete && (
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() => setHardDeleteTarget(m)}
                  title={t('members.deletePermanently')}
                  aria-label={t('members.deletePermanently')}
                >
                  <IconTrash size={18} />
                </ActionIcon>
              )}
            </>
          ) : (
            <>
              {canUpdate && (
                <ActionIcon
                  variant="subtle"
                  onClick={(e) => openEdit(m, e)}
                  title={t('members.editMember')}
                  aria-label={t('members.editMember')}
                >
                  <IconPencil size={18} />
                </ActionIcon>
              )}
              {m.id !== currentUser?.id && canArchive && (
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() => setArchiveTarget(m)}
                  title={t('members.archive', 'Archivieren')}
                  aria-label={t('members.archive', 'Archivieren')}
                >
                  <IconUserX size={18} />
                </ActionIcon>
              )}
            </>
          )}
        </Group>
      </Group>
    </Paper>
  )

  return (
    <div>
      <Group justify="flex-end" mb={16} gap="xs" wrap="nowrap">
        {!showArchived && canExport && (
          <Button variant="default" visibleFrom="sm" onClick={handleExport}>
            <IconUpload size={16} />
            {t('members.export.csv')}
          </Button>
        )}
        {!showArchived && canBulkInvoice && (
          <Button variant="default" visibleFrom="sm" onClick={openBulkInvoice}>
            <IconFileText size={16} />
            {t('members.createInvoices')}
          </Button>
        )}
        {!showArchived && canCreate && (
          <Button
            variant="filled"
            style={{ flex: '1 1 auto', maxWidth: 320 }}
            onClick={() => setAddOpen(true)}
          >
            <IconPlus size={16} />
            {t('common.addMember')}
          </Button>
        )}
        {/* Phones: the less common actions move into a menu. */}
        {!showArchived && (canExport || canBulkInvoice) && (
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon
                variant="default"
                size={36}
                hiddenFrom="sm"
                aria-label={t('common.moreActions', 'Weitere Aktionen')}
              >
                <IconDots size={18} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {canExport && (
                <Menu.Item leftSection={<IconUpload size={16} />} onClick={handleExport}>
                  {t('members.export.csv')}
                </Menu.Item>
              )}
              {canBulkInvoice && (
                <Menu.Item leftSection={<IconFileText size={16} />} onClick={openBulkInvoice}>
                  {t('members.createInvoices')}
                </Menu.Item>
              )}
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>

      <DataTable
        breakpoint="wide"
          columns={[
            {
              key: 'member',
              header: t('common.member'),
              render: (m) => (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  <Avatar
                    name={m.name}
                    color={m.avatarColor}
                    size={32}
                    lastSeen={m.lastSeen}
                  />
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--hb-text)' }}>
                      {m.name}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: 'var(--hb-text-2)',
                      }}
                    >
                      {m.email}
                      {!m.privateEmailVerified && (
                        <span
                          title={t('members.privateEmailUnverified', 'Private E-Mail nicht bestätigt')}
                          style={{
                            color: '#f59e0b',
                            marginLeft: 4,
                            verticalAlign: 'middle',
                          }}
                        >
                          <IconShieldCheckFilled size={13} />
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ),
            },
            {
              key: 'id',
              header: t('members.idCol'),
              render: (m) => (
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--hb-text-3)',
                  }}
                >
                  {m.id}
                </span>
              ),
            },
            {
              key: 'tier',
              header: t('members.tier'),
              render: (m) => <TierTag tier={m.tier} />,
            },
            {
              key: 'groups',
              header: t('members.groupsCol'),
              render: (m) => (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {m.groups.map((g) => (
                    <Tag key={g}>{g}</Tag>
                  ))}
                </div>
              ),
            },
            {
              key: 'joined',
              header: t('members.joined'),
              render: (m) => (
                <span
                  className="num"
                  style={{
                    color: 'var(--hb-text-2)',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {m.joined}
                </span>
              ),
            },
            {
              key: 'status',
              header: t('common.status'),
              render: (m) => <StatusBadge status={m.status} />,
            },
            {
              key: 'actions',
              header: '',
              width: showArchived ? 128 : 80,
              render: (m) => (
                <div onClick={(e) => e.stopPropagation()}>
                  {showArchived ? (
                    <ActionButtons
                      extra={
                        canUnarchive ? (
                          <ActionIcon
                            variant="subtle"
                            size="md"
                            onClick={() => handleUnarchive(m)}
                            title={t('members.restore')}
                          >
                            <IconArchive size={18} />
                          </ActionIcon>
                        ) : undefined
                      }
                      onDelete={
                        canDelete ? () => setHardDeleteTarget(m) : undefined
                      }
                      deleteTitle={t('members.deletePermanently')}
                    />
                  ) : (
                    <ActionButtons
                      onEdit={canUpdate ? () => openEdit(m) : undefined}
                      editTitle={t('members.editMember')}
                      extra={
                        m.id !== currentUser?.id && canArchive ? (
                          <ActionIcon
                            variant="subtle"
                            size="md"
                            color="red"
                            onClick={() => setArchiveTarget(m)}
                            title={t('members.archive')}
                          >
                            <IconUserX size={18} />
                          </ActionIcon>
                        ) : undefined
                      }
                    />
                  )}
                </div>
              ),
            },
          ]}
          data={members}
          loading={membersLoading}
          emptyMessage={t('members.noMembers', 'Keine Mitglieder gefunden.')}
          emptyDescription={
            debouncedSearch || tierFilter !== 'All'
              ? t('members.noMembersFilterHint', 'Ändere die Suche oder den Filter.')
              : undefined
          }
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('members.search')}
          filters={
            showArchived
              ? [
                  {
                    label: t('common.archived'),
                    value: 'archived',
                    active: true,
                    onClick: () => {
                      setShowArchived(false)
                      setTierFilter('All')
                    },
                  },
                ]
              : [
                  ...tiers.map((tier) => ({
                    label: tier === 'All' ? t('common.all', 'Alle') : tier,
                    value: tier.toLowerCase(),
                    active: tierFilter === tier,
                    onClick: () => setTierFilter(tier),
                  })),
                  {
                    label: t('common.archived'),
                    value: 'archived',
                    active: false,
                    onClick: () => {
                      setShowArchived(true)
                      setTierFilter('All')
                    },
                  },
                ]
          }
          page={pg.page}
          perPage={pg.perPage}
          total={pg.total}
          totalPages={pg.totalPages}
          onPageChange={pg.goPage}
          onPerPageChange={pg.setPerPage}
          onRowClick={
            !showArchived ? (m) => go('/app/members/' + m.id, m) : undefined
          }
          getRowKey={(m) => m.id}
          renderCard={renderMemberCard}
          viewKey="members"
          toolbar={
            <Select
              size="xs"
              aria-label={t('members.sort.label', 'Sortieren')}
              data={sortOptions}
              value={sort}
              onChange={(v) => setSort(v ?? '')}
              allowDeselect={false}
              w={170}
            />
          }
        />

      {!showArchived && <Invites />}

      <Modal
        open={bulkInvoiceOpen}
        onClose={() => setBulkInvoiceOpen(false)}
        title={t('members.bulkInvoice.title')}
        footer={
          <>
            <Button variant="default" onClick={() => setBulkInvoiceOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={handleBulkInvoice}
              disabled={bulkSaving || !bulkDue}
            >
              {bulkSaving
                ? t('members.bulkInvoice.creating')
                : t('members.bulkInvoice.createInvoices')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field
            label={t('members.bulkInvoice.tier')}
            hint={t('members.bulkInvoice.tierHint')}
          >
            <Select
              value={bulkTierId}
              onChange={(v) => setBulkTierId(v ?? '')}
              data={[
                {
                  value: '',
                  label: t('members.bulkInvoice.allActiveMembers'),
                },
                ...bulkTiers.map((tierItem) => ({
                  value: tierItem.id,
                  label: `${tierItem.name}${
                    tierItem.priceChf != null
                      ? ` — CHF ${formatCHF(tierItem.priceChf)}`
                      : ` ${t('members.bulkInvoice.noPrice')}`
                  }`,
                })),
              ]}
              searchable
            />
          </Field>
          <Field
            label={t('common.description')}
            hint={t('members.bulkInvoice.descriptionHint')}
          >
            <TextInput
              placeholder={t('members.bulkInvoice.descriptionPlaceholder')}
              value={bulkDescription}
              onChange={(e) => setBulkDescription(e.target.value)}
            />
          </Field>
          <Field label={t('members.bulkInvoice.dueDate')}>
            <TextInput
              type="date"
              value={bulkDue}
              onChange={(e) => setBulkDue(e.target.value)}
            />
          </Field>
          <div
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              color: 'var(--hb-text-2)',
              background: 'var(--hb-surface-2)',
              borderRadius: 8,
              padding: '10px 14px',
            }}
          >
            {t('members.bulkInvoice.note')}
          </div>
        </div>
      </Modal>

      <MemberEditModal
        member={null}
        mode="create"
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSaved={() => {
          // An invite: the member appears once the person accepts.
          queryClient.invalidateQueries({ queryKey: qk.invites })
          setAddOpen(false)
        }}
      />

      <MemberEditModal
        member={editTarget}
        mode="edit"
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: qk.members.all })
          setEditTarget(null)
        }}
      />

      <ConfirmModal
        open={!!archiveTarget}
        onClose={() => setArchiveTarget(null)}
        title={t('members.confirmArchive.title', {
          name: archiveTarget?.name ?? '',
        })}
        body={t('members.confirmArchive.body')}
        onConfirm={confirmArchive}
      />

      <ConfirmModal
        open={!!hardDeleteTarget}
        onClose={() => setHardDeleteTarget(null)}
        title={t('members.confirmDelete.title', {
          name: hardDeleteTarget?.name ?? '',
        })}
        body={t('members.confirmDelete.body')}
        onConfirm={confirmHardDelete}
      />
    </div>
  )
}
