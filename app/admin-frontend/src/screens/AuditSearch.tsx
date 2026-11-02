import { Fragment, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Checkbox,
  Code,
  Group,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { IconDownload, IconSearch } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { Pagination } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr, useLang } from '@/lang'
import {
  exportAudit,
  listTenants,
  searchAudit,
  type AuditSearchEntry,
  type AuditSearchParams,
  type AuditSource,
} from '@/api/tenants'
import { actionColor, actionLabel } from './auditLabels'

function target(e: AuditSearchEntry): string {
  if (e.target_label) return e.target_label
  if (e.target_type) return `${e.target_type}${e.target_id ? ` #${e.target_id}` : ''}`
  return '–'
}

function hasDetails(details: unknown): boolean {
  if (details == null || details === '') return false
  if (typeof details === 'object') return Object.keys(details as object).length > 0
  return true
}

function Row({ entry }: { entry: AuditSearchEntry }) {
  const [open, setOpen] = useState(false)
  const more = hasDetails(entry.details) || !!entry.ip_address || !!entry.actor_email
  return (
    <Fragment>
      <Table.Tr
        style={{ cursor: more ? 'pointer' : undefined, verticalAlign: 'top' }}
        onClick={() => more && setOpen(!open)}
      >
        <Table.Td fz="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
          {entry.time ? formatDateTime(entry.time) : '–'}
        </Table.Td>
        <Table.Td>
          <Group gap={6} wrap="wrap">
            <Badge variant="light" color={actionColor(entry.action)} size="sm" tt="none">
              {actionLabel(entry.action)}
            </Badge>
            <Badge variant="outline" color={entry.source === 'platform' ? 'acc' : 'gray'} size="xs">
              {entry.source === 'platform' ? tr('Plattform', 'Platform') : tr('Verein', 'Club')}
            </Badge>
          </Group>
        </Table.Td>
        <Table.Td fz="sm">{entry.club ?? (entry.tenant_id ? `#${entry.tenant_id}` : '–')}</Table.Td>
        <Table.Td fz="sm">
          {entry.actor ?? (entry.actor_id ? `#${entry.actor_id}` : tr('System', 'System'))}
        </Table.Td>
        <Table.Td fz="sm" c="dimmed" style={{ wordBreak: 'break-word' }}>
          {target(entry)}
        </Table.Td>
      </Table.Tr>
      {open && (
        <Table.Tr>
          <Table.Td colSpan={5}>
            <Text size="xs" c="dimmed" mb={4}>
              {[
                entry.actor_email,
                entry.ip_address ? `IP ${entry.ip_address}` : null,
                `${entry.action}`,
              ]
                .filter(Boolean)
                .join(' · ')}
            </Text>
            {hasDetails(entry.details) && (
              <Code block fz="xs" style={{ whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto' }}>
                {typeof entry.details === 'string'
                  ? entry.details
                  : JSON.stringify(entry.details, null, 2)}
              </Code>
            )}
          </Table.Td>
        </Table.Tr>
      )}
    </Fragment>
  )
}

/** The platform log and every club's audit log in one search, with a CSV
 * export of what the filters leave (services/audit_search.py). */
export function AuditSearch() {
  const { tr: t } = useLang()
  const { notify } = useAdmin()
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [source, setSource] = useState<AuditSource>('all')
  const [club, setClub] = useState<string | null>(null)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [hideLogins, setHideLogins] = useState(true)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  const clubs = useQuery({
    queryKey: ['tenants', 'audit-picker'],
    queryFn: () => listTenants({ per_page: 100, sort_by: 'name', sort_dir: 'asc' }),
    staleTime: 5 * 60_000,
  })

  const filters: AuditSearchParams = {
    q,
    source,
    tenant_id: club ? Number(club) : undefined,
    from: from || undefined,
    to: to || undefined,
    hide_logins: hideLogins,
  }
  const query = useQuery({
    queryKey: ['audit-search', filters, page, perPage],
    queryFn: () => searchAudit({ ...filters, page, per_page: perPage }),
  })
  const entries = query.data?.entries ?? []
  const total = query.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v)
    setPage(1)
  }

  const runExport = async () => {
    setExporting(true)
    try {
      const { rows, truncated } = await exportAudit(filters)
      notify(
        truncated ? 'info' : 'success',
        t(`${rows.toLocaleString('de-CH')} Einträge exportiert`, `${rows.toLocaleString('de-CH')} entries exported`),
        truncated
          ? t(
              'Mehr als 10 000 Einträge: nur die neuesten sind in der Datei. Grenze die Suche ein.',
              'More than 10,000 entries: only the newest are in the file. Narrow the search.',
            )
          : undefined,
      )
    } catch (err) {
      notify('error', t('Export fehlgeschlagen', 'Export failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setExporting(false)
    }
  }

  return (
    <Stack gap={16}>
      <Paper withBorder p="md">
        <Stack gap="sm">
          <Group gap="sm" wrap="wrap" align="flex-end">
            <TextInput
              size="xs"
              leftSection={<IconSearch size={14} />}
              placeholder={t('Aktion, Person, Ziel, Details, IP', 'Action, person, target, details, IP')}
              aria-label={t('Suchen', 'Search')}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
              style={{ flex: '1 1 260px' }}
            />
            <Select
              size="xs"
              aria-label={t('Verein', 'Club')}
              placeholder={t('Alle Vereine', 'All clubs')}
              searchable
              clearable
              value={club}
              onChange={reset(setClub)}
              data={(clubs.data?.tenants ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
              w={220}
            />
            <TextInput
              size="xs"
              type="date"
              label={t('Von', 'From')}
              value={from}
              max={to || undefined}
              onChange={(e) => reset(setFrom)(e.currentTarget.value)}
              w={150}
            />
            <TextInput
              size="xs"
              type="date"
              label={t('Bis', 'To')}
              value={to}
              min={from || undefined}
              onChange={(e) => reset(setTo)(e.currentTarget.value)}
              w={150}
            />
          </Group>
          <Group justify="space-between" gap="sm" wrap="wrap">
            <Group gap="md" wrap="wrap">
              <SegmentedControl
                size="xs"
                value={source}
                onChange={(v) => reset(setSource)(v as AuditSource)}
                data={[
                  { value: 'all', label: t('Alle Protokolle', 'All logs') },
                  { value: 'platform', label: t('Plattform', 'Platform') },
                  { value: 'club', label: t('Vereine', 'Clubs') },
                ]}
              />
              <Checkbox
                size="xs"
                label={t('Anmeldungen ausblenden', 'Hide sign-ins')}
                checked={hideLogins}
                onChange={(e) => reset(setHideLogins)(e.currentTarget.checked)}
              />
            </Group>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconDownload size={14} />}
              loading={exporting}
              disabled={total === 0}
              onClick={runExport}
            >
              {t('Als CSV exportieren', 'Export as CSV')}
            </Button>
          </Group>
        </Stack>
      </Paper>

      <Paper withBorder style={{ overflow: 'hidden' }}>
        {query.isError && (
          <Text p="md" c="red">
            {query.error instanceof Error ? query.error.message : String(query.error)}
          </Text>
        )}
        {query.isLoading && (
          <Text p={40} ta="center" c="dimmed">
            {t('Audit-Log wird geladen …', 'Loading audit log…')}
          </Text>
        )}
        {!query.isLoading && entries.length === 0 && !query.isError && (
          <Text p={40} ta="center" c="dimmed">
            {t('Keine Einträge gefunden.', 'No entries found.')}
          </Text>
        )}
        {entries.length > 0 && (
          <Table.ScrollContainer minWidth={720}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={150}>{t('Zeit', 'Time')}</Table.Th>
                  <Table.Th>{t('Aktion', 'Action')}</Table.Th>
                  <Table.Th>{t('Verein', 'Club')}</Table.Th>
                  <Table.Th>{t('Person', 'Actor')}</Table.Th>
                  <Table.Th>{t('Ziel', 'Target')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {entries.map((e) => (
                  <Row key={e.key} entry={e} />
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        {total > 0 && (
          <Pagination
            page={Math.min(page, totalPages)}
            perPage={perPage}
            total={total}
            totalPages={totalPages}
            goPage={setPage}
            setPerPage={(n: number) => {
              setPerPage(n)
              setPage(1)
            }}
          />
        )}
      </Paper>
    </Stack>
  )
}
