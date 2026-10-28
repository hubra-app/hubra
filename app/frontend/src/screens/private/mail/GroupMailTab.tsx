import { useState, useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconRefresh, IconPlus, IconLoader2 } from '@tabler/icons-react'
import { TextInput, Select, Group, Button, Text } from '@mantine/core'
import { useAuth, useToast } from '@/context/AppContext'
import { Modal, usePagination, DataTable } from '@/components/ui'
import { useMailColumns } from '@/screens/private/mail/MailAddressRow'
import { MailSettingsModal } from '@/screens/private/mail/MailSettingsModal'
import {
  listGroupMail,
  createGroupMail,
  resolveLocalPart,
  type ManagedMailAddressInfo,
} from '@/api/mail'
import { listGroups } from '@/api/groups'

const MAX_GROUP_ALIASES = 10

type SyncFilter = 'all' | 'ok' | 'pending' | 'drift' | 'error'

export function GroupMailTab() {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [syncFilter, setSyncFilter] = useState<SyncFilter>('all')
  const [editEntry, setEditEntry] = useState<ManagedMailAddressInfo | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [newGroupId, setNewGroupId] = useState('')
  const [newPrefix, setNewPrefix] = useState('')
  const [prefixPreview, setPrefixPreview] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const canManage = hasPermission('mail.aliases.create') || hasPermission('mail.aliases.update')

  const {
    data,
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['group-mail'],
    queryFn: () => listGroupMail(),
  })
  const entries = useMemo(() => data ?? [], [data])

  const { data: allGroups = [] } = useQuery({
    queryKey: ['groups'],
    queryFn: () => listGroups(),
  })

  const existingGroupIds = new Set(
    entries.map((e) => e.ownerId).filter((id): id is number => id != null),
  )
  const availableGroups = allGroups.filter((g) => !existingGroupIds.has(Number(g.id)))

  // Count aliases per group for rate limit display.
  const aliasCountsByGroup = useMemo(() => {
    const counts = new Map<number, number>()
    for (const entry of entries) {
      if (entry.ownerId != null) {
        counts.set(entry.ownerId, (counts.get(entry.ownerId) ?? 0) + 1)
      }
    }
    return counts
  }, [entries])

  useEffect(() => {
    if (!newPrefix.trim()) {
      return
    }
    const timer = setTimeout(() => {
      resolveLocalPart(newPrefix.trim())
        .then(setPrefixPreview)
        .catch(() => setPrefixPreview(null))
    }, 300)
    return () => clearTimeout(timer)
  }, [newPrefix])

  const handleCreate = async () => {
    const gid = Number(newGroupId)
    if (!gid) return
    setCreating(true)
    try {
      const created = await createGroupMail(gid, newPrefix.trim())
      queryClient.invalidateQueries({ queryKey: ['group-mail'] })
      setNewGroupId('')
      setNewPrefix('')
      setPrefixPreview(null)
      setCreateOpen(false)
      notify(
        'success',
        t('mail.admin.created', 'Mail erstellt'),
        t('mail.admin.createdMsg', 'Gruppe-Mail {{address}} erstellt.', {
          address: created.address,
        }),
      )
    } catch (err: unknown) {
      const msg =
        err instanceof Error && err.message.includes('429')
          ? t('mail.admin.rateLimited', 'Maximale Aliases für diese Gruppe erreicht.')
          : t('mail.admin.couldNotCreate', 'Gruppe-Mail chonnt n\u00f4d erstellt w\u00f6rde.')
      notify('error', t('common.createFailed', 'Erstelle fehlgeschlage'), msg)
    } finally {
      setCreating(false)
    }
  }

  const filtered = entries.filter((e) => {
    const matchesSearch =
      !search ||
      e.address.toLowerCase().includes(search.toLowerCase()) ||
      (e.groupName || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.displayName || '').toLowerCase().includes(search.toLowerCase())
    const matchesSync = syncFilter === 'all' || (e.syncState ?? 'ok') === syncFilter
    return matchesSearch && matchesSync
  })

  const pg = usePagination(filtered, 25)
  const columns = useMailColumns((e) => e.groupName)

  return (
    <div>
      <Group justify="flex-end" mb={16}>
        <Button variant="default" onClick={() => refetch()} disabled={isFetching}>
          <IconRefresh size={16} className={isFetching ? 'spin' : ''} />
          {t('common.refresh', 'Aktualisiere')}
        </Button>
        {canManage && (
          <Button variant="filled" onClick={() => setCreateOpen(true)}>
            <IconPlus size={16} />
            {t('mail.admin.addGroupMail', 'Gruppe-Mail hinzue')}
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
        searchPlaceholder={t('common.search', 'Sueche�')}
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
        category="group"
        open={!!editEntry}
        onClose={() => setEditEntry(null)}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['group-mail'] })}
        canManage={canManage}
      />

      {createOpen && (
        <Modal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          title={t('mail.admin.createGroupMail', 'Gruppe-Mail erstellen')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
                {t('mail.admin.selectGroup', 'Gruppe usw�hle')}
              </label>
              <Select
                data={[
                  {
                    value: '',
                    label: t('mail.admin.chooseGroup', '– Gruppe –'),
                  },
                  ...availableGroups.map((g) => ({
                    value: g.id,
                    label: g.name,
                  })),
                ]}
                value={newGroupId}
                onChange={(v) => setNewGroupId(v ?? '')}
                searchable
                autoFocus
              />
              {newGroupId && (
                <Text size="xs" c="dimmed" mt={4}>
                  {(() => {
                    const count = aliasCountsByGroup.get(Number(newGroupId)) ?? 0
                    return t('mail.admin.aliasCount', '{{count}} von {{max}} Aliases', {
                      count,
                      max: MAX_GROUP_ALIASES,
                    })
                  })()}
                </Text>
              )}
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
                {t('mail.admin.mailPrefix', 'Mail-Pr�fix')}
              </label>
              <TextInput
                value={newPrefix}
                onChange={(e) => setNewPrefix(e.target.value)}
                placeholder={t('mail.admin.mailPrefixPlaceholder', 'Local part')}
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
                  {t('mail.admin.preview', 'Vorschau')}: <strong>{prefixPreview}</strong>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button variant="default" onClick={() => setCreateOpen(false)}>
                {t('common.cancel', 'Abbr�che')}
              </Button>
              <Button
                variant="filled"
                disabled={
                  creating ||
                  !newGroupId ||
                  !newPrefix.trim() ||
                  (aliasCountsByGroup.get(Number(newGroupId)) ?? 0) >= MAX_GROUP_ALIASES
                }
                onClick={handleCreate}
              >
                {creating ? <IconLoader2 size={16} className="spin" /> : <IconPlus size={16} />}
                {t('common.create', 'Erstellen')}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
