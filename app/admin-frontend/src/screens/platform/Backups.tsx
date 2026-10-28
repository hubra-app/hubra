import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Table, Paper, Badge, Modal, Group, Text, Anchor } from '@mantine/core'
import { Link } from 'react-router-dom'
import {
  IconRefresh,
  IconTrash,
  IconCheck,
  IconX,
  IconClock,
  IconCloudUpload,
  IconAlertTriangle,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { PageHead } from '@/components/ui'
import { useLang, tr } from '@/lang'
import { useState } from 'react'
import {
  listBackups,
  createBackup,
  getBackupConfig,
  verifyBackup,
  deleteBackup,
  type BackupRecord,
} from '@/api/backups'

const TYPE_LABELS: Record<string, [string, string]> = {
  manual: ['Manuell', 'Manual'],
  scheduled_daily: ['Täglich', 'Daily'],
  scheduled_weekly: ['Wöchentlich', 'Weekly'],
  scheduled_monthly: ['Monatlich', 'Monthly'],
}

const STATUS_LABELS: Record<string, [string, string]> = {
  pending: ['Wartet', 'Pending'],
  running: ['Läuft', 'Running'],
  completed: ['Fertig', 'Completed'],
  failed: ['Fehlgeschlagen', 'Failed'],
}

function label(map: Record<string, [string, string]>, key: string): string {
  const l = map[key]
  return l ? tr(l[0], l[1]) : key
}

const TYPE_COLORS: Record<string, string> = {
  manual: '#5e5873',
  scheduled_daily: '#2596be',
  scheduled_weekly: '#27ae60',
  scheduled_monthly: '#9b59b6',
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#c2870f',
  running: '#2596be',
  completed: '#1f9d57',
  failed: '#c0392b',
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('de-CH', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Backups of the whole database (every club), for platform staff. Where
 * they go is set under Platform Settings; the passphrase stays in env.
 */
export function Backups() {
  const { notify } = useAdmin()
  const { tr } = useLang()
  const queryClient = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<BackupRecord | null>(null)
  const [creating, setCreating] = useState(false)
  const [verifyingId, setVerifyingId] = useState<string | null>(null)

  const configQuery = useQuery({
    queryKey: ['backup-config'],
    queryFn: () => getBackupConfig(),
  })

  const hasPending = (data: BackupRecord[] | undefined) =>
    (data ?? []).some((b) => b.status === 'pending' || b.status === 'running')

  const backupsQuery = useQuery({
    queryKey: ['backups'],
    queryFn: () => listBackups(),
    refetchInterval: (query) => (hasPending(query.state.data) ? 5000 : false),
  })

  const config = configQuery.data ?? null
  const backups = backupsQuery.data ?? []

  const handleCreate = async () => {
    setCreating(true)
    try {
      await createBackup()
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      notify('success', tr('Backup gestartet', 'Backup started'), tr('Ein neues Backup wird erstellt.', 'A new backup is being created.'))
    } catch (err: unknown) {
      notify('error', tr('Backup fehlgeschlagen', 'Backup failed'), err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error'))
    } finally {
      setCreating(false)
    }
  }

  const handleVerify = async (id: string) => {
    setVerifyingId(id)
    try {
      await verifyBackup(id)
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      notify('success', tr('Prüfung gestartet', 'Verification started'), tr('Das Backup wird geprüft.', 'Backup verification is running.'))
    } catch (err: unknown) {
      notify('error', tr('Prüfung fehlgeschlagen', 'Verify failed'), err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error'))
    } finally {
      setVerifyingId(null)
    }
  }

  const handleDelete = async (record: BackupRecord) => {
    try {
      await deleteBackup(record.id)
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      setDeleteTarget(null)
      notify('success', tr('Gelöscht', 'Deleted'), tr(`Backup #${record.id} wurde gelöscht.`, `Backup #${record.id} removed.`))
    } catch (err: unknown) {
      notify('error', tr('Löschen fehlgeschlagen', 'Delete failed'), err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error'))
    }
  }

  const configReady = config?.s3_configured && config?.encryption_configured
  const configPartial = config?.s3_configured && !config?.encryption_configured

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <PageHead
        title={tr('Backups', 'Backups')}
        desc={
          <>
            {tr(
              'Jedes Backup enthält die ganze Datenbank mit allen Vereinen, verschlüsselt mit BACKUP_ENCRYPTION_KEY aus der Umgebung. Tägliche, wöchentliche und monatliche Backups laufen von selbst; den Speicherort legst du unter ',
              'Each backup holds the whole database, every club included, encrypted with BACKUP_ENCRYPTION_KEY from env. Daily, weekly and monthly backups run on their own; the storage is set under ',
            )}
            <Anchor component={Link} to="/app/platform/settings" size="sm">
              {tr('Plattform-Einstellungen', 'Platform settings')}
            </Anchor>
            {tr(' fest.', '.')}
          </>
        }
      />
      {/* ── Config status banner ─────────────────────────────────────── */}
      {configQuery.isLoading && (
        <div style={{ color: '#8c86a0', fontSize: 'var(--mantine-font-size-sm)' }}>
          {tr('Backup-Einstellungen werden geladen …', 'Loading backup configuration…')}
        </div>
      )}

      {config && (
        <Paper withBorder shadow="sm" radius="lg" style={{ padding: '1rem 1.25rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              flexWrap: 'wrap',
            }}
          >
            {configReady ? (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    background: '#e6f7ed',
                    color: '#1a7d43',
                    fontSize: 'var(--mantine-font-size-sm)',
                  },
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                  }}
                >
                  <IconCheck size={12} /> {tr('Backup eingerichtet', 'Backup configured')}
                </span>
              </Badge>
            ) : configPartial ? (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    background: '#fff3e0',
                    color: '#e65100',
                    fontSize: 'var(--mantine-font-size-sm)',
                  },
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                  }}
                >
                  <IconAlertTriangle size={12} /> {tr('Schlüssel fehlt', 'Encryption key missing')}
                </span>
              </Badge>
            ) : (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    background: '#ffebee',
                    color: '#c0392b',
                    fontSize: 'var(--mantine-font-size-sm)',
                  },
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                  }}
                >
                  <IconAlertTriangle size={12} /> {tr('S3 nicht eingerichtet', 'S3 not configured')}
                </span>
              </Badge>
            )}

            {config.s3_reachable && (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    background: '#e6f7ed',
                    color: '#1a7d43',
                    fontSize: 'var(--mantine-font-size-xs)',
                  },
                }}
              >
                {tr('S3 erreichbar', 'S3 reachable')}
              </Badge>
            )}
            {config.s3_configured && !config.s3_reachable && (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    background: '#ffebee',
                    color: '#c0392b',
                    fontSize: 'var(--mantine-font-size-xs)',
                  },
                }}
              >
                {tr('S3 nicht erreichbar', 'S3 unreachable')}
              </Badge>
            )}

            {config.bucket && (
              <span
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: '#5e5873',
                }}
              >
                {config.bucket}
              </span>
            )}

            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <Button
                variant="subtle"
                size="sm"
                leftSection={<IconRefresh size={14} />}
                onClick={() => {
                  configQuery.refetch()
                  backupsQuery.refetch()
                }}
                loading={configQuery.isFetching || backupsQuery.isFetching}
              >
                {tr('Aktualisieren', 'Refresh')}
              </Button>
              <Button
                variant="filled"
                size="sm"
                leftSection={<IconCloudUpload size={14} />}
                onClick={handleCreate}
                loading={creating}
                disabled={!configReady}
              >
                {tr('Jetzt sichern', 'Create backup now')}
              </Button>
            </div>
          </div>

          {config.s3_error && (
            <div
              style={{
                marginTop: 8,
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#c0392b',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {config.s3_error}
            </div>
          )}

          {!configReady && (
            <div
              style={{
                marginTop: 8,
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#5e5873',
              }}
            >
              {tr(
                'Lege den Speicher unter Plattform-Einstellungen fest und setze BACKUP_ENCRYPTION_KEY in der .env, um Backups einzuschalten.',
                'Set the storage under Platform settings and BACKUP_ENCRYPTION_KEY in .env to enable backups.',
              )}
            </div>
          )}
        </Paper>
      )}

      {/* ── Backups table ────────────────────────────────────────────── */}
      <Paper withBorder shadow="sm" radius="lg">
        <Table highlightOnHover className="responsive-table">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>#</Table.Th>
              <Table.Th>{tr('Datum', 'Date')}</Table.Th>
              <Table.Th>{tr('Art', 'Type')}</Table.Th>
              <Table.Th>{tr('Status', 'Status')}</Table.Th>
              <Table.Th>{tr('Grösse', 'Size')}</Table.Th>
              <Table.Th>{tr('Geprüft', 'Verified')}</Table.Th>
              <Table.Th>{tr('Tabellen', 'Tables')}</Table.Th>
              <Table.Th style={{ width: 100 }}>{tr('Aktionen', 'Actions')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {backups.length === 0 && !backupsQuery.isLoading && (
              <Table.Tr>
                <Table.Td colSpan={8}>
                  <div
                    style={{
                      padding: '32px 16px',
                      textAlign: 'center',
                      color: '#8c86a0',
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {tr('Noch keine Backups. Mit «Jetzt sichern» legst du das erste an.', 'No backups yet. Click "Create backup now" to start.')}
                  </div>
                </Table.Td>
              </Table.Tr>
            )}

            {backups.map((b) => (
              <Table.Tr key={b.id}>
                <Table.Td data-label="#" style={{ color: '#5e5873' }}>
                  {b.id}
                </Table.Td>
                <Table.Td data-label="Date">{formatDate(b.created_at)}</Table.Td>
                <Table.Td data-label="Type">
                  <span
                    style={{
                      background: TYPE_COLORS[b.type] ?? '#5e5873',
                      color: '#fff',
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: 5,
                      display: 'inline-block',
                    }}
                  >
                    {label(TYPE_LABELS, b.type)}
                  </span>
                </Table.Td>
                <Table.Td data-label="Status">
                  <span
                    style={{
                      color: STATUS_COLORS[b.status] ?? '#5e5873',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {b.status === 'pending' || b.status === 'running' ? (
                      <IconClock size={13} />
                    ) : null}
                    {label(STATUS_LABELS, b.status)}
                  </span>
                  {b.error_message && (
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#c0392b',
                        marginTop: 2,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {b.error_message}
                    </div>
                  )}
                </Table.Td>
                <Table.Td data-label="Size" style={{ color: '#5e5873' }}>
                  {formatSize(b.size_bytes)}
                </Table.Td>
                <Table.Td data-label="Verified">
                  {b.verified_ok === true && (
                    <span
                      style={{
                        color: '#1a7d43',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <IconCheck size={14} /> {formatDate(b.verified_at)}
                    </span>
                  )}
                  {b.verified_ok === false && (
                    <span
                      style={{
                        color: '#c0392b',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                      title={b.verify_error ?? ''}
                    >
                      <IconX size={14} /> {tr('Fehlgeschlagen', 'Failed')}
                    </span>
                  )}
                  {b.verified_ok === null && <span style={{ color: '#bbb' }}>—</span>}
                </Table.Td>
                <Table.Td data-label="Tables" style={{ color: '#5e5873' }}>
                  {b.table_count ?? '—'}
                </Table.Td>
                <Table.Td data-label="Actions">
                  <div style={{ display: 'flex', gap: 4 }}>
                    {b.status === 'completed' && b.verified_ok === null && (
                      <Button
                        variant="subtle"
                        size="compact-sm"
                        onClick={() => handleVerify(b.id)}
                        loading={verifyingId === b.id}
                        style={{ padding: '2px 6px' }}
                        title={tr('Backup prüfen', 'Verify backup')}
                      >
                        {tr('Prüfen', 'Verify')}
                      </Button>
                    )}
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      onClick={() => setDeleteTarget(b)}
                      style={{ padding: '2px 6px', color: '#c0392b' }}
                      title={tr('Backup löschen', 'Delete backup')}
                    >
                      <IconTrash size={14} />
                    </Button>
                  </div>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>

      <Modal
        opened={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title={tr('Backup löschen', 'Delete backup')}
      >
        <Text size="sm" mb="lg">
          {deleteTarget
            ? tr(
                `Backup #${deleteTarget.id} vom ${formatDate(deleteTarget.created_at)} löschen? Die Datei im S3-Speicher wird entfernt, das lässt sich nicht rückgängig machen.`,
                `Delete backup #${deleteTarget.id} from ${formatDate(deleteTarget.created_at)}? This removes the S3 object and cannot be undone.`,
              )
            : ''}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setDeleteTarget(null)}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            color="red"
            onClick={() => {
              if (deleteTarget) handleDelete(deleteTarget)
            }}
          >
            {tr('Löschen', 'Delete')}
          </Button>
        </Group>
      </Modal>
    </div>
  )
}
