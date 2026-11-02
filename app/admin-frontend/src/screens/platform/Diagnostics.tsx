import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Modal,
  Paper,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconBolt, IconRefresh, IconSearch, IconTrash } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { Pagination } from '@/components/ui'
import { tr } from '@/lang'
import {
  deleteMailServerOrphan,
  getApiPermissions,
  getMailServer,
  getPlatformHealth,
  reconcileMailServer,
  type MailServerEntry,
} from '@/api/platform'
import { Row } from './StatusRow'
import { BuildsPanel } from './Builds'

const MONO = "'JetBrains Mono', monospace"

// Called at render time so the labels follow the chosen language.
const serviceLabel = (key: string): string =>
  ({
    db: tr('Datenbank', 'Database'),
    redis: 'Redis',
    smtp: tr('Mail-Relay', 'Mail relay'),
    imap: 'IMAP',
  })[key] ?? key

function failureText(err: unknown) {
  return err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error')
}

// ── System health ────────────────────────────────────────────────────────────

export function HealthPanel() {
  const healthQuery = useQuery({ queryKey: ['platform-health'], queryFn: getPlatformHealth })
  const navigate = useNavigate()
  const health = healthQuery.data

  return (
    <Stack gap={16}>
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group justify="space-between" mb={8}>
          <Title order={3}>{tr('Systemzustand', 'System health')}</Title>
          <Button
            variant="subtle"
            size="sm"
            leftSection={<IconRefresh size={14} />}
            onClick={() => healthQuery.refetch()}
            loading={healthQuery.isFetching}
          >
            {tr('Aktualisieren', 'Refresh')}
          </Button>
        </Group>
        {healthQuery.isLoading && <Text c="dimmed">{tr('Wird geprüft …', 'Checking…')}</Text>}
        {healthQuery.isError && (
          <Text c="red">{failureText(healthQuery.error)}</Text>
        )}
        {health && (
          <>
            <Row ok={health.status === 'ok' ? true : health.status === 'degraded' ? null : false} label={tr('Gesamt', 'Overall')}>
              <Text size="sm" fw={600} tt="capitalize">
                {health.status}
              </Text>
            </Row>
            <Row ok={!health.stale} label={tr('Hintergrundprüfung', 'Background check')}>
              <Text size="sm">
                {health.stale
                  ? tr(
                      'Läuft nicht: der Celery-Beat hat seit über einer Minute nichts gemeldet.',
                      'Not running: Celery beat has not reported for over a minute.',
                    )
                  : tr('Läuft alle 20 Sekunden', 'Runs every 20 seconds')}
              </Text>
            </Row>
            <Row ok={null} label={tr('Backend-Version', 'Backend version')}>
              <Group gap={10} wrap="wrap">
                <Text size="sm" ff={MONO}>
                  {health.version ?? '—'}
                </Text>
                <Button variant="subtle" size="compact-xs" onClick={() => navigate('/app/whats-new')}>
                  {tr('Änderungen ansehen', 'See the changelog')}
                </Button>
              </Group>
            </Row>
            {Object.entries(health.services).map(([key, svc]) => (
              <Row key={key} ok={svc.ok} label={serviceLabel(key)}>
                <Group gap={10} wrap="wrap">
                  <Text size="sm" fw={600} c={svc.ok ? 'green.8' : 'red.8'}>
                    {svc.ok ? 'OK' : tr('Fehler', 'Failed')}
                  </Text>
                  <Text size="xs" c="dimmed" ff={MONO}>
                    {svc.latency_ms} ms
                  </Text>
                  {svc.error && (
                    <Text size="xs" c="red.8" style={{ wordBreak: 'break-word' }}>
                      {svc.error}
                    </Text>
                  )}
                </Group>
              </Row>
            ))}
          </>
        )}
      </Paper>

      {health && <BuildsPanel health={health} />}
    </Stack>
  )
}

// ── Mail server ──────────────────────────────────────────────────────────────

function formatQuota(used: number | null, total: number | null) {
  if (used === null || total === null) return '—'
  const mb = (n: number) => `${Math.round(n / (1024 * 1024))} MB`
  return `${mb(used)} / ${mb(total)}`
}

export function MailServerPanel() {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const [search, setSearch] = useState('')
  const [onlyOrphans, setOnlyOrphans] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<MailServerEntry | null>(null)
  const [busy, setBusy] = useState(false)

  // 503 when the instance has no mail server: show that at once, no retries.
  const query = useQuery({ queryKey: ['mail-server'], queryFn: getMailServer, retry: false })
  const entries = query.data ?? []
  const q = search.trim().toLowerCase()
  const filtered = entries.filter(
    (e) =>
      (!onlyOrphans || !e.managed) &&
      (!q ||
        e.address.toLowerCase().includes(q) ||
        (e.ownerName ?? '').toLowerCase().includes(q) ||
        (e.club?.name ?? '').toLowerCase().includes(q)),
  )
  const orphanCount = entries.filter((e) => !e.managed).length

  const reconcile = async () => {
    setBusy(true)
    try {
      await reconcileMailServer()
      notify(
        'success',
        tr('Abgleich gestartet', 'Reconcile started'),
        tr('Alle Vereine werden im Hintergrund abgeglichen.', 'Every club is reconciled in the background.'),
      )
    } catch (err) {
      notify('error', tr('Abgleich fehlgeschlagen', 'Reconcile failed'), failureText(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!deleteTarget) return
    setBusy(true)
    try {
      await deleteMailServerOrphan(deleteTarget.type, deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['mail-server'] })
      notify('success', tr('Entfernt', 'Removed'), deleteTarget.address)
      setDeleteTarget(null)
    } catch (err) {
      notify('error', tr('Löschen fehlgeschlagen', 'Delete failed'), failureText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap={16}>
      <Group justify="space-between" wrap="wrap">
        <Group gap="xs" wrap="wrap">
          <TextInput
            leftSection={<IconSearch size={16} />}
            placeholder={tr('Adresse, Verein oder Person', 'Address, club or person')}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            w={280}
          />
          <Button
            variant={onlyOrphans ? 'filled' : 'default'}
            size="sm"
            onClick={() => setOnlyOrphans((v) => !v)}
          >
            {tr(`Nur verwaiste (${orphanCount})`, `Orphans only (${orphanCount})`)}
          </Button>
        </Group>
        <Group gap="xs">
          <Button
            variant="default"
            leftSection={<IconRefresh size={16} />}
            onClick={() => query.refetch()}
            loading={query.isFetching}
          >
            {tr('Aktualisieren', 'Refresh')}
          </Button>
          {canChange && (
            <Button leftSection={<IconBolt size={16} />} onClick={reconcile} loading={busy}>
              {tr('Jetzt abgleichen', 'Reconcile now')}
            </Button>
          )}
        </Group>
      </Group>

      {query.isError && <Text c="red">{failureText(query.error)}</Text>}

      <Paper withBorder shadow="sm" radius="lg">
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Typ', 'Type')}</Table.Th>
                <Table.Th>{tr('Adresse', 'Address')}</Table.Th>
                <Table.Th>{tr('Verein', 'Club')}</Table.Th>
                <Table.Th>{tr('Zugehörig zu', 'Belongs to')}</Table.Th>
                <Table.Th>{tr('Ziele', 'Targets')}</Table.Th>
                <Table.Th>{tr('Speicher', 'Quota')}</Table.Th>
                {canChange && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {query.isLoading && (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text c="dimmed" size="sm">
                      {tr('Wird geladen …', 'Loading…')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
              {!query.isLoading && filtered.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text c="dimmed" size="sm">
                      {tr('Keine Einträge.', 'No entries.')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
              {filtered.map((e) => (
                <Table.Tr key={`${e.type}-${e.id}`}>
                  <Table.Td>
                    <Badge variant="light" color={e.type === 'mailbox' ? 'green' : 'blue'}>
                      {e.type === 'mailbox' ? tr('Postfach', 'Mailbox') : 'Alias'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" ff={MONO}>
                      {e.address}
                    </Text>
                    {e.disabled && (
                      <Text size="xs" c="dimmed">
                        {tr('deaktiviert', 'disabled')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {e.managed ? (
                      <Text size="sm">{e.club?.name ?? '—'}</Text>
                    ) : (
                      <Badge variant="light" color="orange">
                        {tr('verwaist', 'orphan')}
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{e.ownerName ?? '—'}</Text>
                    {e.kind && (
                      <Text size="xs" c="dimmed">
                        {e.kind}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" ff={MONO} style={{ wordBreak: 'break-all' }}>
                      {e.targets.join(', ') || '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" ff={MONO}>
                      {formatQuota(e.quotaUsed, e.quotaTotal)}
                    </Text>
                  </Table.Td>
                  {canChange && (
                    <Table.Td>
                      {!e.managed && (
                        <Button
                          variant="subtle"
                          color="red"
                          size="xs"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => setDeleteTarget(e)}
                        >
                          {tr('Löschen', 'Delete')}
                        </Button>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
      </Paper>

      <Modal
        opened={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title={tr('Verwaisten Eintrag löschen?', 'Delete orphan entry?')}
      >
        <Text size="sm" mb="md">
          {tr(
            `${deleteTarget?.address} gehört keinem Verein. Das Löschen entfernt es samt allen Mails vom Mailserver und lässt sich nicht rückgängig machen.`,
            `${deleteTarget?.address} belongs to no club. Deleting removes it and all its mail from the mail server and cannot be undone.`,
          )}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setDeleteTarget(null)}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button color="red" onClick={remove} loading={busy}>
            {tr('Löschen', 'Delete')}
          </Button>
        </Group>
      </Modal>
    </Stack>
  )
}

// ── API permissions ──────────────────────────────────────────────────────────

const METHOD_COLORS: Record<string, string> = {
  GET: 'green',
  POST: 'blue',
  PATCH: 'yellow',
  PUT: 'yellow',
  DELETE: 'red',
}

export function PermissionsPanel() {
  const query = useQuery({ queryKey: ['api-permissions'], queryFn: getApiPermissions })
  const [search, setSearch] = useState('')
  const [method, setMethod] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (query.data ?? []).filter(
      (e) =>
        (!method || e.method === method) &&
        (!q ||
          e.path.toLowerCase().includes(q) ||
          e.key.toLowerCase().includes(q) ||
          e.display_name.toLowerCase().includes(q)),
    )
  }, [query.data, search, method])
  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage))
  const current = Math.min(page, totalPages)
  const paged = filtered.slice((current - 1) * perPage, current * perPage)
  const pager = {
    page: current,
    perPage,
    total: filtered.length,
    totalPages,
    goPage: setPage,
    setPerPage: (n: number) => {
      setPerPage(n)
      setPage(1)
    },
  }

  return (
    <Stack gap={16}>
      <Text c="dimmed" size="sm" maw={720}>
        {tr(
          'Welche Vereinsberechtigung jeden Endpunkt der Vereins-API schützt. Die Vereine vergeben diese Berechtigungen über ihre Rollen.',
          'Which club permission guards each endpoint of the club API. Clubs grant these permissions through their roles.',
        )}
      </Text>
      <Group gap="xs" wrap="wrap">
        <TextInput
          leftSection={<IconSearch size={16} />}
          placeholder={tr('Pfad oder Berechtigung', 'Path or permission')}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value)
            setPage(1)
          }}
          w={280}
        />
        {['', 'GET', 'POST', 'PATCH', 'PUT', 'DELETE'].map((m) => (
          <Button
            key={m || 'all'}
            size="xs"
            variant={method === m ? 'filled' : 'default'}
            onClick={() => {
              setMethod(m)
              setPage(1)
            }}
          >
            {m || tr('Alle', 'All')}
          </Button>
        ))}
        <Text size="sm" c="dimmed" ml="auto">
          {filtered.length} {tr('Endpunkte', 'endpoints')}
        </Text>
      </Group>
      {query.isError && <Text c="red">{failureText(query.error)}</Text>}
      <Paper withBorder shadow="sm" radius="lg">
        <Pagination {...pager} />
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={90}>{tr('Methode', 'Method')}</Table.Th>
                <Table.Th>{tr('Pfad', 'Path')}</Table.Th>
                <Table.Th>{tr('Berechtigung', 'Permission')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {paged.map((e) => (
                <Table.Tr key={`${e.method}:${e.path}`}>
                  <Table.Td>
                    <Badge variant="filled" color={METHOD_COLORS[e.method] ?? 'gray'} ff={MONO}>
                      {e.method}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" ff={MONO}>
                      {e.path}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {e.display_name}
                    </Text>
                    <Text size="xs" c="dimmed" ff={MONO}>
                      {e.key}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>
        <Pagination {...pager} />
      </Paper>
    </Stack>
  )
}
