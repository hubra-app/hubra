import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Table, Paper, Badge } from '@mantine/core'
import {
  IconRefresh,
  IconTrash,
  IconCheck,
  IconX,
  IconClock,
  IconCloudUpload,
  IconAlertTriangle,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { ConfirmModal } from '@/components/ui'
import { useState } from 'react'
import {
  listBackups,
  createBackup,
  getBackupConfig,
  verifyBackup,
  deleteBackup,
  type BackupRecord,
} from '@/api/backups'

const TYPE_LABELS: Record<string, string> = {
  manual: 'Manual',
  scheduled_daily: 'Daily',
  scheduled_weekly: 'Weekly',
  scheduled_monthly: 'Monthly',
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
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function BackupsTab() {
  const { t } = useT()
  const { notify } = useToast()
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
      notify('success', 'Backup started', 'A new backup is being created.')
    } catch (err: unknown) {
      notify(
        'error',
        'Backup failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setCreating(false)
    }
  }

  const handleVerify = async (id: string) => {
    setVerifyingId(id)
    try {
      await verifyBackup(id)
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      notify(
        'success',
        'Verification started',
        'Backup verification is running.',
      )
    } catch (err: unknown) {
      notify(
        'error',
        'Verify failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setVerifyingId(null)
    }
  }

  const handleDelete = async (record: BackupRecord) => {
    try {
      await deleteBackup(record.id)
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      setDeleteTarget(null)
      notify('success', 'Deleted', `Backup #${record.id} removed.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Delete failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    }
  }

  const configReady = config?.s3_configured && config?.encryption_configured
  const configPartial = config?.s3_configured && !config?.encryption_configured

  return (
    <div
      style={{
        marginTop: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      {/* ── Config status banner ─────────────────────────────────────── */}
      {configQuery.isLoading && (
        <div
          style={{ color: '#8c86a0', fontSize: 'var(--mantine-font-size-sm)' }}
        >
          Loading backup configuration…
        </div>
      )}

      {config && (
        <Paper
          withBorder
          shadow="sm"
          radius="lg"
          style={{ padding: '1rem 1.25rem' }}
        >
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
                  <IconCheck size={12} /> Backup configured
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
                  <IconAlertTriangle size={12} /> Encryption key missing
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
                  <IconAlertTriangle size={12} /> S3 not configured
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
                S3 reachable
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
                S3 unreachable
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
                {t('common.refresh', 'Aktualisieren')}
              </Button>
              <Button
                variant="filled"
                size="sm"
                leftSection={<IconCloudUpload size={14} />}
                onClick={handleCreate}
                loading={creating}
                disabled={!configReady}
              >
                Create backup now
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
              Configure S3 settings in the Settings tab (backup namespace) and
              set BACKUP_ENCRYPTION_KEY in .env to enable backups.
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
              <Table.Th>Date</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Size</Table.Th>
              <Table.Th>Verified</Table.Th>
              <Table.Th>Tables</Table.Th>
              <Table.Th style={{ width: 100 }}>Actions</Table.Th>
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
                    No backups yet. Click "Create backup now" to start.
                  </div>
                </Table.Td>
              </Table.Tr>
            )}

            {backups.map((b) => (
              <Table.Tr key={b.id}>
                <Table.Td data-label="#" style={{ color: '#5e5873' }}>
                  {b.id}
                </Table.Td>
                <Table.Td data-label="Date">
                  {formatDate(b.created_at)}
                </Table.Td>
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
                    {TYPE_LABELS[b.type] ?? b.type}
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
                    {b.status.charAt(0).toUpperCase() + b.status.slice(1)}
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
                      <IconX size={14} /> Failed
                    </span>
                  )}
                  {b.verified_ok === null && (
                    <span style={{ color: '#bbb' }}>—</span>
                  )}
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
                        title="Verify backup"
                      >
                        Verify
                      </Button>
                    )}
                    <Button
                      variant="subtle"
                      size="compact-sm"
                      onClick={() => setDeleteTarget(b)}
                      style={{ padding: '2px 6px', color: '#c0392b' }}
                      title="Delete backup"
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

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete backup"
        body={
          deleteTarget
            ? `Delete backup #${deleteTarget.id} from ${formatDate(
                deleteTarget.created_at,
              )}? This removes the S3 object and cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget)
        }}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}
