import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconRefresh,
  IconTrash,
  IconBolt,
  IconSearch,
} from '@tabler/icons-react'
import { Table, TextInput, Button, Group, Paper, Badge } from '@mantine/core'
import { useToast, useAuth } from '@/context/AppContext'
import {
  ConfirmModal,
  LoadingSpinner,
  EmptyState,
} from '@/components/ui'
import {
  listWildDuckLive,
  deleteWildDuckOrphan,
  triggerReconcile,
  type WildDuckLiveEntry,
} from '@/api/mail'

export function WildDuckLiveTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<WildDuckLiveEntry | null>(
    null,
  )
  const [busy, setBusy] = useState(false)

  const canDelete = hasPermission('mail.wildduck.delete')
  const canReconcile = hasPermission('mail.reconcile.run')

  const {
    data: entries = [],
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['wildduck-live'],
    queryFn: () => listWildDuckLive(),
  })

  const filtered = entries.filter(
    (e) =>
      !search ||
      e.address.toLowerCase().includes(search.toLowerCase()) ||
      (e.ownerName || '').toLowerCase().includes(search.toLowerCase()),
  )

  const handleReconcile = async () => {
    setBusy(true)
    try {
      await triggerReconcile()
      notify(
        'success',
        t('mail.admin.reconcileStarted', 'Reconcile gstartet'),
        t(
          'mail.admin.reconcileStartedMsg',
          'D Sync-Uftrag isch in Warte-Schlange plaziert.',
        ),
      )
    } catch {
      notify(
        'error',
        t('common.error', 'Fehler'),
        t(
          'mail.admin.couldNotReconcile',
          'Reconcile chonnt nöd gstartet wärde.',
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleDeleteOrphan = async () => {
    if (!deleteTarget) return
    setBusy(true)
    try {
      await deleteWildDuckOrphan(deleteTarget.type, deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['wildduck-live'] })
      notify(
        'info',
        t('mail.admin.orphanDeleted', 'Orphan entfernt'),
        t('mail.admin.orphanDeletedMsg', '{{address}} isch entfernet worde.', {
          address: deleteTarget.address,
        }),
      )
    } catch {
      notify(
        'error',
        t('common.deleteFailed', 'Lösche fehlgeschlage'),
        t('mail.admin.couldNotDeleteOrphan', 'Orphan chonnt nöd gösche wärde.'),
      )
    } finally {
      setBusy(false)
      setDeleteTarget(null)
    }
  }

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
        {canReconcile && (
          <Button
            variant="filled"
            onClick={handleReconcile}
            disabled={busy}
          >
            <IconBolt size={16} />
            {t('mail.admin.reconcileNow', 'Reconcile jetzt')}
          </Button>
        )}
      </Group>

      <Paper
        withBorder
        shadow="sm"
        radius="lg"
        style={{ marginBottom: 16, padding: 12 }}
      >
        <div style={{ position: 'relative', maxWidth: 400 }}>
          <IconSearch
            size={16}
            style={{
              position: 'absolute',
              left: 10,
              top: 10,
              color: '#99a2ac',
            }}
          />
          <TextInput
            style={{ paddingLeft: 32 }}
            placeholder={t('common.search', 'Sueche…')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </Paper>

      {loading ? (
        <LoadingSpinner />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={t('common.noResults', 'Keini Resultat')}
          description={t(
            'mail.admin.noEntries',
            'Keini WildDuck-Iiträg gfunde.',
          )}
        />
      ) : (
        <Paper withBorder shadow="sm" radius="lg">
          <div style={{ overflowX: 'auto' }}>
            <Table highlightOnHover className="responsive-table">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('mail.admin.type', 'Typ')}</Table.Th>
                  <Table.Th>{t('mail.address', 'Adr??�sse')}</Table.Th>
                  <Table.Th>{t('mail.admin.managed', 'Verwaltet')}</Table.Th>
                  <Table.Th>{t('mail.admin.category', 'Kategorie')}</Table.Th>
                  <Table.Th>{t('mail.admin.owner', 'Besitzer')}</Table.Th>
                  <Table.Th>{t('mail.admin.targets', 'Targets')}</Table.Th>
                  <Table.Th>{t('mail.admin.quota', 'Quota')}</Table.Th>
                  <Table.Th>{t('common.actions', 'Aktione')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filtered.map((e) => (
                  <Table.Tr key={`${e.type}-${e.id}`}>
                    <Table.Td data-label={t('mail.admin.type', 'Typ')}>
                      <Badge
                        variant="light"
                        radius="xl"
                        styles={{
                          root: {
                            background:
                              e.type === 'mailbox' ? '#e8f5e9' : '#e3f2fd',
                            color: e.type === 'mailbox' ? '#1f9d57' : '#2596be',
                          },
                        }}
                      >
                        {e.type === 'mailbox'
                          ? t('mail.admin.mailbox', 'Mailbox')
                          : t('mail.admin.alias', 'Alias')}
                      </Badge>
                    </Table.Td>
                    <Table.Td
                      data-label={t('mail.address', 'Adr??sse')}
                      style={{
                        fontSize: 'var(--mantine-font-size-sm)',
                        color: '#181818',
                      }}
                    >
                      {e.address}
                    </Table.Td>
                    <Table.Td data-label={t('mail.admin.managed', 'Verwaltet')}>
                      {e.managed ? (
                        <Badge variant="light" color="green" radius="xl">
                          {t('mail.admin.managedYes', 'Verwaltet')}
                        </Badge>
                      ) : (
                        <Badge
                          variant="light"
                          radius="xl"
                          styles={{
                            root: { background: '#fff3e0', color: '#e65100' },
                          }}
                        >
                          {t('mail.admin.orphan', 'Orphan')}
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td
                      data-label={t('mail.admin.category', 'Kategorie')}
                    >
                      {(() => {
                        const kindColors: Record<
                          string,
                          { bg: string; fg: string }
                        > = {
                          member: { bg: '#e3f2fd', fg: '#2596be' },
                          group: { bg: '#e8f5e9', fg: '#1f9d57' },
                          function: { bg: '#f3e5f5', fg: '#9c27b0' },
                          system: { bg: '#eceff1', fg: '#607d8b' },
                          orphan: { bg: '#fff3e0', fg: '#e65100' },
                        }
                        const kindKey = e.kind || 'orphan'
                        const kc = kindColors[kindKey] || kindColors.system
                        return (
                          <Badge
                            variant="light"
                            radius="xl"
                            styles={{
                              root: { background: kc.bg, color: kc.fg },
                            }}
                          >
                            {kindKey.charAt(0).toUpperCase() + kindKey.slice(1)}
                          </Badge>
                        )
                      })()}
                    </Table.Td>
                    <Table.Td
                      data-label={t('mail.admin.owner', 'Besitzer')}
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#6b7480',
                      }}
                    >
                      {e.ownerName || e.name || '\u2014'}
                    </Table.Td>
                    <Table.Td
                      data-label={t('mail.admin.targets', 'Targets')}
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#6b7480',
                      }}
                    >
                      {e.targets.length > 0 ? e.targets.join(', ') : '—'}
                    </Table.Td>
                    <Table.Td
                      data-label={t('mail.admin.quota', 'Quota')}
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#6b7480',
                      }}
                    >
                      {e.quotaUsed != null && e.quotaTotal != null
                        ? `${(e.quotaUsed / 1048576).toFixed(0)}/${(
                            e.quotaTotal / 1048576
                          ).toFixed(0)} MB`
                        : '—'}
                    </Table.Td>
                    <Table.Td data-label={t('common.actions', 'Aktione')}>
                      {e.managed ? (
                        <span
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#99a2ac',
                          }}
                        >
                          {t(
                            'mail.admin.editInCategory',
                            'I Kategorie-Tab bearbeite',
                          )}
                        </span>
                      ) : canDelete ? (
                        <Button
                          size="sm"
                          variant="light"
                          color="red"
                          onClick={() => setDeleteTarget(e)}
                        >
                          <IconTrash size={16} />
                          {t('common.delete', 'Lösche')}
                        </Button>
                      ) : null}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </div>
        </Paper>
      )}

      <ConfirmModal
        open={!!deleteTarget}
        title={t('mail.admin.deleteOrphanTitle', 'Orphan entferne')}
        body={t(
          'mail.admin.deleteOrphanBody',
          'D WildDuck-Adrässe {{address}} wird permanent entfernet.',
          { address: deleteTarget?.address || '' },
        )}
        onConfirm={handleDeleteOrphan}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}
