import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Code,
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
import { PageHead, Pagination, Tabs } from '@/components/ui'
import { useLang, tr } from '@/lang'
import {
  deleteMailServerOrphan,
  getApiPermissions,
  getChangelog,
  getMailServer,
  getPlatformHealth,
  reconcileMailServer,
  type MailServerEntry,
} from '@/api/platform'

const MONO = "'JetBrains Mono', monospace"

const SERVICE_LABELS: Record<string, string> = {
  db: 'Datenbank / Database',
  redis: 'Redis',
  smtp: 'Mail-Relay / Mail relay',
  imap: 'IMAP',
}

function Dot({ ok }: { ok: boolean | null }) {
  const color = ok === null ? '#c2870f' : ok ? '#1f9d57' : '#c0392b'
  return (
    <span
      style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }}
    />
  )
}

function Row({ ok, label, children }: { ok: boolean | null; label: string; children: React.ReactNode }) {
  return (
    <Group gap={12} wrap="nowrap" py={8} style={{ borderBottom: '1px solid #f0eef6' }}>
      <Dot ok={ok} />
      <Text size="sm" c="dimmed" miw={160}>
        {label}
      </Text>
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </Group>
  )
}

function failureText(err: unknown) {
  return err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error')
}

// ── System health ────────────────────────────────────────────────────────────

function HealthPanel() {
  const healthQuery = useQuery({ queryKey: ['platform-health'], queryFn: getPlatformHealth })
  const changelogQuery = useQuery({ queryKey: ['changelog'], queryFn: getChangelog })
  const [showAllVersions, setShowAllVersions] = useState(false)
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
              <Text size="sm" ff={MONO}>
                {health.version ?? '—'}
              </Text>
            </Row>
            {Object.entries(health.services).map(([key, svc]) => (
              <Row key={key} ok={svc.ok} label={SERVICE_LABELS[key] ?? key}>
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

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={12}>
          {tr('Änderungen', 'Changelog')}
        </Title>
        {(changelogQuery.data?.entries ?? []).length === 0 && (
          <Text c="dimmed" size="sm">
            {tr('Keine Einträge.', 'No entries.')}
          </Text>
        )}
        <Stack gap={16}>
          {(changelogQuery.data?.entries ?? [])
            .slice(0, showAllVersions ? undefined : 3)
            .map((entry) => (
            <div key={entry.version}>
              <Group gap={8} mb={6}>
                <Text fw={700} size="sm">
                  v{entry.version}
                </Text>
                {entry.date && (
                  <Text size="xs" c="dimmed">
                    {entry.date}
                  </Text>
                )}
              </Group>
              {Object.entries(entry.sections).map(([section, items]) => (
                <div key={section} style={{ marginLeft: 12, marginBottom: 6 }}>
                  <Text size="xs" fw={600} c="dimmed" tt="uppercase">
                    {section}
                  </Text>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {items.map((item, i) => (
                      <li key={item + i}>
                        <Text size="sm" style={{ overflowWrap: 'anywhere' }}>
                          <InlineMarkdown text={item} />
                        </Text>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
          {(changelogQuery.data?.entries ?? []).length > 3 && (
            <Button
              variant="subtle"
              size="compact-sm"
              style={{ alignSelf: 'flex-start' }}
              onClick={() => setShowAllVersions((v) => !v)}
            >
              {showAllVersions
                ? tr('Nur die neusten Versionen', 'Only the latest versions')
                : tr('Alle Versionen zeigen', 'Show all versions')}
            </Button>
          )}
        </Stack>
      </Paper>
    </Stack>
  )
}

/** **bold** and `code` from changelog lines, as text (never as HTML). */
function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**') ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : part.startsWith('`') && part.endsWith('`') ? (
          <Code key={i}>{part.slice(1, -1)}</Code>
        ) : (
          part
        ),
      )}
    </>
  )
}

// ── Mail server ──────────────────────────────────────────────────────────────

function formatQuota(used: number | null, total: number | null) {
  if (used === null || total === null) return '—'
  const mb = (n: number) => `${Math.round(n / (1024 * 1024))} MB`
  return `${mb(used)} / ${mb(total)}`
}

function MailServerPanel() {
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

function PermissionsPanel() {
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

// ── Page ─────────────────────────────────────────────────────────────────────

const TABS = ['health', 'mail-server', 'permissions'] as const
type Tab = (typeof TABS)[number]

/** Diagnostics of the whole instance, for platform staff (platform.diagnostics). */
export function Diagnostics() {
  const { tr } = useLang()
  const location = useLocation()
  const navigate = useNavigate()
  const last = location.pathname.split('/').pop() as Tab
  const tab: Tab = TABS.includes(last) ? last : 'health'

  return (
    <div>
      <PageHead
        title={tr('Diagnose', 'Diagnostics')}
        desc={tr(
          'Zustand der Plattform für alle Vereine: Dienste, der gemeinsame Mailserver und die Berechtigungen der Vereins-API.',
          'The state of the platform for every club: services, the shared mail server and the permissions of the club API.',
        )}
      />
      <Tabs
        tabs={[
          { id: 'health', label: tr('Systemzustand', 'System health') },
          { id: 'mail-server', label: tr('Mailserver', 'Mail server') },
          { id: 'permissions', label: tr('API-Berechtigungen', 'API permissions') },
        ]}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/platform/diagnostics/${id}`)}
      />
      {tab === 'health' && <HealthPanel />}
      {tab === 'mail-server' && <MailServerPanel />}
      {tab === 'permissions' && <PermissionsPanel />}
    </div>
  )
}
