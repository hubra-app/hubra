import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconRefresh, IconPlus, IconLoader2 } from '@tabler/icons-react'
import { TextInput, Select, Group, Button } from '@mantine/core'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, usePagination, DataTable } from '@/components/ui'
import { useMailColumns } from '@/screens/private/mail/useMailColumns'
import { MailSettingsModal } from '@/screens/private/mail/MailSettingsModal'
import {
  listSystemAddresses,
  createSystemAddress,
  type ManagedMailAddressInfo,
} from '@/api/mail'
import { qk } from '@/data/keys'

type SyncFilter = 'all' | 'ok' | 'pending' | 'drift' | 'error'

export function SystemMailTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [syncFilter, setSyncFilter] = useState<SyncFilter>('all')
  const [editEntry, setEditEntry] = useState<ManagedMailAddressInfo | null>(
    null,
  )
  const [createOpen, setCreateOpen] = useState(false)
  const [newAddr, setNewAddr] = useState('')
  const [newType, setNewType] = useState('mailbox')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [creating, setCreating] = useState(false)

  const canManage = hasPermission('mail.system.manage')

  const {
    data,
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: qk.mail.systemAddresses,
    queryFn: () => listSystemAddresses(),
  })
  const entries = data ?? []

  const filtered = entries.filter((e) => {
    const matchesSearch =
      !search ||
      e.address.toLowerCase().includes(search.toLowerCase()) ||
      (e.displayName || '').toLowerCase().includes(search.toLowerCase())
    const matchesSync =
      syncFilter === 'all' || (e.syncState ?? 'ok') === syncFilter
    return matchesSearch && matchesSync
  })

  const pg = usePagination(filtered, 25)
  const columns = useMailColumns((e) => e.displayName)

  const handleCreate = async () => {
    const addr = newAddr.trim()
    if (!addr) return
    setCreating(true)
    try {
      const created = await createSystemAddress({
        address: addr,
        addressType: newType,
        displayName: newDisplayName.trim() || undefined,
        isProtected: false,
      })
      queryClient.invalidateQueries({ queryKey: qk.mail.systemAddresses })
      setNewAddr('')
      setNewDisplayName('')
      setNewType('mailbox')
      setCreateOpen(false)
      notify(
        'success',
        t('mail.system.address.createdLabel', 'System-Adresse erstellt'),
        t(
          'mail.system.address.created.msg',
          'System-Adresse {{address}} erstellt.',
          { address: created.address },
        ),
      )
    } catch (e: unknown) {
      const msg =
        e instanceof Error
          ? e.message
          : t(
              'mail.could.not.create.system.address',
              'System-Adresse konnte nicht erstellt werden.',
            )
      notify('error', t('common.createFailed', 'Erstellen fehlgeschlagen'), msg)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <Group justify="flex-end" mb={16} className="page-actions">
        <Button
          variant="default"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <IconRefresh size={16} className={isFetching ? 'spin' : ''} />
          {t('common.refresh', 'Aktualisieren')}
        </Button>
        {canManage && (
          <Button variant="filled" onClick={() => setCreateOpen(true)}>
            <IconPlus size={16} />
            {t('mail.add.system.address', 'System-Adresse hinzufügen')}
          </Button>
        )}
      </Group>

      <DataTable
        breakpoint="xwide"
        columns={columns}
        data={pg.paged}
        loading={loading}
        emptyMessage={t('common.noResults', 'Keine Ergebnisse.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('common.search', 'Suchen')}
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
                label: t('mail.admin.syncAll', 'Alle Zustände'),
              },
              { value: 'ok', label: t('mail.admin.syncOk', 'OK') },
              {
                value: 'pending',
                label: t('mail.admin.syncPending', 'Ausstehend'),
              },
              {
                value: 'drift',
                label: t('mail.admin.syncDrift', 'Abweichung'),
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
        category="system"
        open={!!editEntry}
        onClose={() => setEditEntry(null)}
        onSaved={() =>
          queryClient.invalidateQueries({ queryKey: qk.mail.systemAddresses })
        }
        canManage={canManage}
      />

      {createOpen && (
        <Modal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          title={t('mail.create.system.address', 'System-Adresse erstellen')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#2e2940',
                  marginBottom: 4,
                  display: 'block',
                }}
              >
                {t('mail.address', 'Adresse')}
              </label>
              <TextInput
                placeholder="noreply@example.org"
                value={newAddr}
                onChange={(e) => setNewAddr(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                autoFocus
              />
            </div>
            <div>
              <label
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#2e2940',
                  marginBottom: 4,
                  display: 'block',
                }}
              >
                {t('mail.typeLabel', 'Typ')}
              </label>
              <Select
                data={[
                  {
                    value: 'mailbox',
                    label: t('mail.type.mailbox', 'Postfach'),
                  },
                  { value: 'alias', label: t('mail.type.alias', 'Alias') },
                ]}
                value={newType}
                onChange={(v) => v && setNewType(v)}
              />
            </div>
            <div>
              <label
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#2e2940',
                  marginBottom: 4,
                  display: 'block',
                }}
              >
                {t('mail.display.name', 'Anzeigename')}
              </label>
              <TextInput
                placeholder="No Reply"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              />
            </div>
            <div
              style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}
            >
              <Button variant="default" onClick={() => setCreateOpen(false)}>
                {t('common.cancel', 'Abbrechen')}
              </Button>
              <Button
                variant="filled"
                disabled={creating || !newAddr.trim()}
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
          </div>
        </Modal>
      )}
    </div>
  )
}
