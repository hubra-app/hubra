import { useState, useEffect, useMemo } from 'react'
import { Button, Group, Menu, Select, Paper, TextInput, ActionIcon } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconPlus,
  IconSearch,
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
  Seg,
  Tag,
  usePagination,
  Pagination,
  ConfirmModal,
  DataTable,
  ActionButtons,
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
import { getLookups } from '@/api/lookups'
import { formatCHF } from '@/format'
import { MemberEditModal } from '@/components/MemberEditModal'

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
  const [view, setView] = useState<'table' | 'cards'>('cards')
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
    queryKey: qk.lookups,
    queryFn: () => getLookups(),
  })
  const allTiers = useMemo(
    () =>
      lookupsData
        ? [...lookupsData.tiersByName.keys()]
        : ['Maker', 'Pro', 'Student', 'Workshop'],
    [lookupsData],
  )
  const tierColors = useMemo(() => {
    if (!lookupsData) return {}
    const colors: Record<string, string> = {}
    lookupsData.tiers.forEach((tier) => {
      colors[tier.name] = tier.color
    })
    return colors
  }, [lookupsData])

  const { data: bulkTiers = [] } = useQuery({
    queryKey: qk.tiers.all,
    queryFn: () => listTiers(),
    enabled: bulkInvoiceOpen,
  })

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [search])

  const { data: membersData } = useQuery({
    queryKey: qk.members.list(debouncedSearch, tierFilter, showArchived),
    queryFn: () =>
      listMembers({
        search: debouncedSearch,
        tier: tierFilter,
        archived: showArchived,
      }),
  })
  const members = membersData?.members ?? []

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
  const pg = usePagination(members, 25)

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

      {view === 'table' ? (
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
                    <div style={{ fontWeight: 600, color: '#1a1625' }}>
                      {m.name}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#5e5873',
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
                    color: '#8c86a0',
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
                    color: '#5e5873',
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
          data={pg.paged}
          emptyMessage={t('members.noMembers', 'Keine Mitglieder gefunden.')}
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
                    label: tier,
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
          toolbar={
            <Seg
              options={[
                {
                  value: 'table',
                  label: '≡ ' + t('members.tableView'),
                },
                {
                  value: 'cards',
                  label: '⊞ ' + t('members.cardsView'),
                },
              ]}
              value={view}
              onChange={(v) => setView(v as 'table' | 'cards')}
            />
          }
        />
      ) : (
        <Paper withBorder shadow="sm" radius="lg">
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid #d6d2e3',
              display: 'flex',
              gap: 10,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <TextInput
              style={{ flex: '1 1 220px' }}
              leftSection={<IconSearch size={16} />}
              placeholder={t('members.search')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {!showArchived &&
                tiers.map((tier) => (
                  <button
                    key={tier}
                    className={`chip${tierFilter === tier ? ' on' : ''}`}
                    onClick={() => setTierFilter(tier)}
                  >
                    {tier !== 'All' && (
                      <span
                        className="dot"
                        style={{ background: tierColors[tier] ?? '#857f99' }}
                      />
                    )}
                    {tier === 'All' ? t('common.all', 'Alle') : tier}
                  </button>
                ))}
              <button
                className={`chip${showArchived ? ' on' : ''}`}
                style={
                  showArchived
                    ? {
                        borderColor: '#ff4d3d',
                        color: '#ff4d3d',
                        background: '#fff1f0',
                      }
                    : {}
                }
                onClick={() => {
                  setShowArchived((v) => !v)
                  setTierFilter('All')
                }}
              >
                <IconUserX size={16} />
                {t('common.archived')}
              </button>
            </div>
            <div
              style={{
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#5e5873',
                }}
              >
                {t('members.shown', { count: members.length })}
              </span>
              <Seg
                options={[
                  { value: 'table', label: '≡ ' + t('members.tableView') },
                  { value: 'cards', label: '⊞ ' + t('members.cardsView') },
                ]}
                value={view}
                onChange={(v) => setView(v as 'table' | 'cards')}
              />
            </div>
          </div>

          <>
            <Pagination {...pg} top />
            <div
              style={{
                padding: 16,
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                gap: 12,
              }}
            >
              {pg.paged.map((m) => (
                <Paper
                  key={m.id}
                  withBorder
                  shadow="sm"
                  radius="lg"
                  style={{
                    padding: 16,
                    cursor: showArchived ? 'default' : 'pointer',
                  }}
                  onClick={() => !showArchived && go('/app/members/' + m.id, m)}
                >
                  <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                    <Avatar
                      name={m.name}
                      color={m.avatarColor}
                      size={40}
                      lastSeen={m.lastSeen}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          color: '#1a1625',
                          fontSize: 'var(--mantine-font-size-sm)',
                        }}
                      >
                        {m.name}
                      </div>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: '#5e5873',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
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
                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      flexWrap: 'wrap',
                      marginBottom: 10,
                    }}
                  >
                    <TierTag tier={m.tier} />
                    <StatusBadge status={m.status} />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      borderTop: '1px solid #e6e3ef',
                      paddingTop: 10,
                      marginTop: 2,
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {showArchived ? (
                      <>
                        {canUnarchive && (
                          <Button
                            size="sm"
                            variant="subtle"
                            style={{ flex: 1 }}
                            onClick={() => handleUnarchive(m)}
                          >
                            <IconArchive size={16} />
                            {t('members.restore')}
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            size="sm"
                            variant="subtle"
                            style={{ color: '#ff4d3d' }}
                            onClick={() => setHardDeleteTarget(m)}
                          >
                            <IconTrash size={16} />
                          </Button>
                        )}
                      </>
                    ) : (
                      <>
                        {canUpdate && (
                          <Button
                            size="sm"
                            variant="subtle"
                            style={{ flex: 1 }}
                            onClick={(e) => openEdit(m, e)}
                          >
                            <IconPencil size={16} />
                            {t('members.editMember')}
                          </Button>
                        )}
                        {m.id !== currentUser?.id && canArchive && (
                          <Button
                            size="sm"
                            variant="subtle"
                            style={{ color: '#ff4d3d' }}
                            onClick={(e) => {
                              e.stopPropagation()
                              setArchiveTarget(m)
                            }}
                          >
                            <IconUserX size={16} />
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </Paper>
              ))}
            </div>
            <Pagination {...pg} />
          </>
        </Paper>
      )}

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
              color: '#5e5873',
              background: '#f4f2f9',
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
