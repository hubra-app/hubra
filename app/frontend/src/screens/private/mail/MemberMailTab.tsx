import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconSearch,
  IconRefresh,
  IconPlus,
  IconLoader2,
} from '@tabler/icons-react'
import { TextInput, Select, Group, Button } from '@mantine/core'
import { useAuth, useToast } from '@/context/AppContext'
import { Modal, usePagination, DataTable } from '@/components/ui'
import { useMailColumns } from '@/screens/private/mail/MailAddressRow'
import { MailSettingsModal } from '@/screens/private/mail/MailSettingsModal'
import {
  listMemberMailMma,
  createMemberMail,
  resolveLocalPart,
  type ManagedMailAddressInfo,
} from '@/api/mail'
import { listMembers } from '@/api/members'

type SyncFilter = 'all' | 'ok' | 'pending' | 'drift' | 'error'

export function MemberMailTab() {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [syncFilter, setSyncFilter] = useState<SyncFilter>('all')
  const [editEntry, setEditEntry] = useState<ManagedMailAddressInfo | null>(
    null,
  )
  const [createOpen, setCreateOpen] = useState(false)
  const [memberSearch, setMemberSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedMemberId, setSelectedMemberId] = useState('')
  const [newPrefix, setNewPrefix] = useState('')
  const [prefixPreview, setPrefixPreview] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const canManage = hasPermission('mail.member_mail.update')

  const {
    data,
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['member-mail-mma'],
    queryFn: () => listMemberMailMma(),
  })
  const entries = data ?? []

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(memberSearch), 250)
    return () => clearTimeout(timer)
  }, [memberSearch])

  const { data: memberSearchData } = useQuery({
    queryKey: ['members-search-mail', debouncedSearch],
    queryFn: () => listMembers({ search: debouncedSearch, pageSize: 20 }),
    enabled: debouncedSearch.length >= 2,
  })

  const existingMemberIds = new Set(
    entries.map((e) => e.ownerId).filter((id): id is number => id != null),
  )
  const searchResults = (memberSearchData?.members ?? []).filter(
    (m) => !existingMemberIds.has(Number(m.id)),
  )

  useEffect(() => {
    if (!newPrefix.trim()) {
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      resolveLocalPart(newPrefix.trim())
        .then((v) => {
          if (!cancelled) setPrefixPreview(v)
        })
        .catch(() => {
          if (!cancelled) setPrefixPreview(null)
        })
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [newPrefix])

  const handleSelectMember = (id: string, name: string) => {
    setSelectedMemberId(id)
    const autoPrefix = name
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '.')
      .replace(/\.+/g, '.')
      .replace(/^\.|\.$/g, '')
    setNewPrefix(autoPrefix)
  }

  const handleCreate = async () => {
    const mid = Number(selectedMemberId)
    if (!mid) return
    setCreating(true)
    try {
      const created = await createMemberMail(mid, newPrefix.trim())
      queryClient.invalidateQueries({ queryKey: ['member-mail-mma'] })
      setSelectedMemberId('')
      setMemberSearch('')
      setNewPrefix('')
      setPrefixPreview(null)
      setCreateOpen(false)
      notify(
        'success',
        t('mail.admin.created', 'Mail erstellt'),
        t('mail.admin.createdMsg', 'Mitglied-Mail {{address}} erstellt.', {
          address: created.address,
        }),
      )
    } catch {
      notify(
        'error',
        t('common.createFailed', 'Erstellen fehlgeschlagen'),
        t(
          'mail.admin.couldNotCreate',
          'Mitglied-Mail chonnt n?d erstellt w?rde.',
        ),
      )
    } finally {
      setCreating(false)
    }
  }

  const filtered = entries.filter((e) => {
    const matchesSearch =
      !search ||
      e.address.toLowerCase().includes(search.toLowerCase()) ||
      (e.memberName || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.displayName || '').toLowerCase().includes(search.toLowerCase())
    const matchesSync =
      syncFilter === 'all' || (e.syncState ?? 'ok') === syncFilter
    return matchesSearch && matchesSync
  })

  const pg = usePagination(filtered, 25)
  const columns = useMailColumns((e) => e.memberName)

  return (
    <div>
      <Group justify="flex-end" mb={16}>
        <Button
          variant="default"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <IconRefresh size={16} className={isFetching ? 'spin' : ''} />
          {t('common.refresh', 'Aktualisiere')}
        </Button>
        {canManage && (
          <Button variant="filled" onClick={() => setCreateOpen(true)}>
            <IconPlus size={16} />
            {t('mail.admin.addMemberMail', 'Mitglied-Mail hinzue')}
          </Button>
        )}
      </Group>

      <DataTable
        breakpoint="xwide"
        columns={columns}
        data={pg.paged}
        loading={loading}
        emptyMessage={t('common.noResults', 'Keini Resultat')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('common.search', 'Sueche?')}
        page={pg.page}
        perPage={pg.perPage}
        total={pg.total}
        totalPages={pg.totalPages}
        onPageChange={pg.goPage}
        onPerPageChange={pg.setPerPage}
        onRowClick={(entry) => setEditEntry(entry)}
        getRowKey={(entry) => entry.id}
        toolbar={
          <Select
            size="sm"
            style={{ width: 'auto', minWidth: 140 }}
            data={[
              {
                value: 'all',
                label: t('mail.admin.syncAll', 'All Sync-Zueständ'),
              },
              { value: 'ok', label: t('mail.admin.syncOk', 'OK') },
              {
                value: 'pending',
                label: t('mail.admin.syncPending', 'Usstehend'),
              },
              {
                value: 'drift',
                label: t('mail.admin.syncDrift', 'Abwichig'),
              },
              { value: 'error', label: t('mail.admin.syncError', 'Fehler') },
            ]}
            value={syncFilter}
            onChange={(v) => setSyncFilter((v ?? 'all') as SyncFilter)}
          />
        }
      />

      <MailSettingsModal
        key={editEntry?.id}
        entry={editEntry}
        category="member"
        open={!!editEntry}
        onClose={() => setEditEntry(null)}
        onSaved={() =>
          queryClient.invalidateQueries({ queryKey: ['member-mail-mma'] })
        }
        canManage={canManage}
      />

      {createOpen && (
        <Modal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          title={t('mail.admin.createMemberMail', 'Mitglied-Mail erstellen')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {!selectedMemberId ? (
              <div>
                <label
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 600,
                    color: '#3a4048',
                    marginBottom: 4,
                    display: 'block',
                  }}
                >
                  {t('mail.admin.searchMember', 'Mitglied sueche')}
                </label>
                <div style={{ position: 'relative' }}>
                  <TextInput
                    style={{ paddingLeft: 32 }}
                    placeholder={t(
                      'mail.admin.searchMemberPlaceholder',
                      'Name oder E-Mail…',
                    )}
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    autoFocus
                  />
                  <IconSearch
                    size={16}
                    style={{
                      position: 'absolute',
                      left: 10,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: '#99a2ac',
                    }}
                  />
                </div>
                {searchResults.length > 0 && (
                  <div
                    style={{
                      marginTop: 4,
                      border: '1px solid #d3ddd7',
                      borderRadius: 8,
                      overflow: 'hidden',
                      background: 'white',
                      maxHeight: 200,
                      overflowY: 'auto',
                    }}
                  >
                    {searchResults.map((m) => (
                      <Button
                        key={m.id}
                        variant="subtle"
                        style={{
                          width: '100%',
                          justifyContent: 'flex-start',
                          padding: '8px 12px',
                          borderRadius: 0,
                          borderBottom: '1px solid #e3eae6',
                        }}
                        onClick={() => handleSelectMember(m.id, m.name)}
                      >
                        {m.name}
                        {m.publicEmail && (
                          <span
                            style={{
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: '#99a2ac',
                              marginLeft: 8,
                            }}
                          >
                            {m.publicEmail}
                          </span>
                        )}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    background: '#f4f8f5',
                    borderRadius: 6,
                  }}
                >
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      fontWeight: 600,
                    }}
                  >
                    {memberSearchData?.members?.find(
                      (m) => m.id === selectedMemberId,
                    )?.name ?? selectedMemberId}
                  </span>
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => {
                      setSelectedMemberId('')
                      setNewPrefix('')
                      setPrefixPreview(null)
                    }}
                  >
                    {t('common.change', 'Ändere')}
                  </Button>
                </div>
                <div>
                  <label
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      fontWeight: 600,
                      color: '#3a4048',
                      marginBottom: 4,
                      display: 'block',
                    }}
                  >
                    {t('mail.admin.mailPrefix', 'Mail-Pr?fix')}
                  </label>
                  <TextInput
                    value={newPrefix}
                    onChange={(e) => setNewPrefix(e.target.value)}
                    placeholder={t(
                      'mail.admin.mailPrefixPlaceholder',
                      'Local part',
                    )}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  />
                  {prefixPreview && (
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#2596be',
                        padding: '6px 10px',
                        background: '#f0f7ff',
                        borderRadius: 6,
                        marginTop: 4,
                      }}
                    >
                      {t('mail.admin.preview', 'Vorschau')}:{' '}
                      <strong>{prefixPreview}</strong>
                    </div>
                  )}
                </div>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 8,
                  }}
                >
                  <Button
                    variant="default"
                    onClick={() => setCreateOpen(false)}
                  >
                    {t('common.cancel', 'Abbr?che')}
                  </Button>
                  <Button
                    variant="filled"
                    disabled={creating || !newPrefix.trim()}
                    onClick={handleCreate}
                  >
                    {creating ? (
                      <IconLoader2 size={16} className="spin" />
                    ) : (
                      <IconPlus size={16} />
                    )}
                    {t('common.create', 'Erstellen')}
                  </Button>
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
