import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import {
  Badge,
  Button,
  Code,
  Group,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { IconCheck, IconRefresh, IconRotate } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { Pagination } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr, useLang } from '@/lang'
import { FilterBar } from '@/components/FilterBar'
import {
  getError,
  getErrors,
  setErrorStatus,
  type ErrorGroupRow,
  type ErrorStatus,
} from '@/api/platform'
import { CommitLink } from './Builds'

const MONO = "'JetBrains Mono', monospace"

type Sort = 'last_seen' | 'count' | 'first_seen'

function failureText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}

/** The traceback, the builds it happened on and the release that brought it. */
function ErrorDetail({
  group,
  canChange,
  onChanged,
}: {
  group: ErrorGroupRow
  canChange: boolean
  onChanged: () => void
}) {
  const { notify } = useAdmin()
  const [busy, setBusy] = useState(false)
  const query = useQuery({ queryKey: ['platform-error', group.id], queryFn: () => getError(group.id) })
  const detail = query.data?.error
  const builds = Object.entries(group.builds).reverse()

  const change = async () => {
    setBusy(true)
    try {
      await setErrorStatus(group.id, group.status === 'open' ? 'resolve' : 'reopen')
      notify(
        'success',
        group.status === 'open'
          ? tr('Als behoben markiert', 'Marked as resolved')
          : tr('Wieder offen', 'Open again'),
      )
      onChanged()
    } catch (err) {
      notify('error', tr('Hat nicht geklappt', 'That did not work'), failureText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap={12} mt={10}>
      {query.isError && <Text c="red">{failureText(query.error)}</Text>}
      {detail?.traceback && (
        <Code block fz="xs" style={{ whiteSpace: 'pre-wrap', maxHeight: 280, overflow: 'auto' }}>
          {detail.traceback}
        </Code>
      )}
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <Stack gap={4}>
          <Text size="xs" fw={600} c="dimmed" tt="uppercase">
            {tr('Eingeführt mit', 'Introduced in')}
          </Text>
          <Group gap={6}>
            <Text size="sm" ff={MONO}>
              {group.first_build.split(' ')[0]}
            </Text>
            <CommitLink sha={group.first_commit} />
          </Group>
          <Text size="xs" c="dimmed">
            {detail?.release
              ? tr(
                  `Upgrade vom ${formatDateTime(detail.release.at)}`,
                  `Upgrade of ${formatDateTime(detail.release.at)}`,
                )
              : tr(
                  'Kein Upgrade im Ereignisprotokoll gefunden',
                  'No upgrade found in the event log',
                )}
          </Text>
          {detail?.last_club && (
            <Text size="xs" c="dimmed">
              {tr(`Zuletzt bei ${detail.last_club.name}`, `Last seen at ${detail.last_club.name}`)}
            </Text>
          )}
        </Stack>
        <Table withRowBorders={false} verticalSpacing={2}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th fz="xs">{tr('Version', 'Build')}</Table.Th>
              <Table.Th fz="xs" ta="right">
                {tr('Anzahl', 'Count')}
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {builds.map(([label, n]) => (
              <Table.Tr key={label}>
                <Table.Td fz="sm" ff={MONO}>
                  {label}
                </Table.Td>
                <Table.Td fz="sm" ta="right" className="num">
                  {n.toLocaleString('de-CH')}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </SimpleGrid>
      {canChange && (
        <Group justify="flex-end">
          <Button
            size="xs"
            variant="light"
            loading={busy}
            leftSection={group.status === 'open' ? <IconCheck size={14} /> : <IconRotate size={14} />}
            onClick={change}
          >
            {group.status === 'open'
              ? tr('Als behoben markieren', 'Mark as resolved')
              : tr('Wieder öffnen', 'Reopen')}
          </Button>
        </Group>
      )}
    </Stack>
  )
}

function ErrorRow({
  group,
  canChange,
  onChanged,
}: {
  group: ErrorGroupRow
  canChange: boolean
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Table.Tr style={{ verticalAlign: 'top', cursor: 'pointer' }} onClick={() => setOpen(!open)}>
      <Table.Td>
        <Group gap={6} wrap="wrap">
          <Text fz="sm" fw={600} ff={MONO} style={{ wordBreak: 'break-all' }}>
            {group.exc_type}
          </Text>
          {group.new_in_current && (
            <Badge size="sm" variant="light" color="orange">
              {tr('Neu in dieser Version', 'New in this build')}
            </Badge>
          )}
          {group.status === 'open' && group.reopened_at && (
            <Badge size="sm" variant="light" color="red">
              {tr('Wieder aufgetreten', 'Came back')}
            </Badge>
          )}
        </Group>
        <Text fz="sm" c="red" style={{ wordBreak: 'break-word' }} lineClamp={open ? undefined : 2}>
          {group.message || tr('(keine Meldung)', '(no message)')}
        </Text>
        <Text fz="xs" ff={MONO} mt={2} style={{ wordBreak: 'break-all' }}>
          {group.route}
        </Text>
        {group.location && (
          <Text fz="xs" c="dimmed" ff={MONO} style={{ wordBreak: 'break-all' }}>
            {group.location}
          </Text>
        )}
        {open && (
          <div onClick={(e) => e.stopPropagation()} style={{ cursor: 'auto' }}>
            <ErrorDetail group={group} canChange={canChange} onChanged={onChanged} />
          </div>
        )}
      </Table.Td>
      <Table.Td className="num" ta="right" fz="sm" fw={600}>
        {group.count.toLocaleString('de-CH')}
      </Table.Td>
      <Table.Td fz="sm" ff={MONO} style={{ whiteSpace: 'nowrap' }}>
        {group.first_build}
      </Table.Td>
      <Table.Td fz="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
        {formatDateTime(group.last_seen)}
      </Table.Td>
    </Table.Tr>
  )
}

/**
 * Unexpected API errors (answered 500), grouped by type, route and place in
 * the code, with the build each first happened on (services/error_tracker.py).
 */
export function ErrorsPanel() {
  const { tr: t } = useLang()
  const { hasGlobalPermission } = useAdmin()
  const canChange = hasGlobalPermission('platform.settings')
  const queryClient = useQueryClient()
  // ?q= from links (API errors page): search it, open and resolved alike.
  const linkedQ = new URLSearchParams(useLocation().search).get('q')?.trim() ?? ''
  const [status, setStatus] = useState<ErrorStatus | 'all'>(linkedQ ? 'all' : 'open')
  const [search, setSearch] = useState(linkedQ)
  const [q, setQ] = useState(linkedQ)
  const [sort, setSort] = useState<Sort>('last_seen')
  const [build, setBuild] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)

  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  const query = useQuery({
    queryKey: ['platform-errors', status, q, sort, build, page, perPage],
    queryFn: () =>
      getErrors({ status, q, sort, build: build ?? undefined, page, per_page: perPage }),
    refetchInterval: 30_000,
  })
  const data = query.data
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['platform-errors'] })
    queryClient.invalidateQueries({ queryKey: ['platform-error'] })
  }
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const buildOptions = Object.entries(data?.builds ?? {})
    .reverse()
    .map(([label, n]) => ({
      value: label,
      label:
        label === data?.current_build
          ? t(`${label} · läuft jetzt (${n})`, `${label} · running now (${n})`)
          : `${label} (${n})`,
    }))

  return (
    <Stack gap={20}>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Text c="dimmed" size="sm" maw={720}>
          {t(
            `Fehler, die die API nicht abfangen konnte (Antwort 500). Gleicher Typ, gleiche Route und gleiche Stelle im Code sind eine Gruppe. Läuft gerade: ${data?.current_build ?? '…'}.`,
            `Errors the API did not handle (answered 500). Same type, same route and same place in the code are one group. Running now: ${data?.current_build ?? '…'}.`,
          )}
        </Text>
        <Button
          variant="subtle"
          size="xs"
          leftSection={<IconRefresh size={14} />}
          onClick={() => query.refetch()}
          loading={query.isFetching}
        >
          {t('Aktualisieren', 'Refresh')}
        </Button>
      </Group>

      <Group gap="sm" wrap="wrap" align="flex-start">
        <SegmentedControl
          size="sm"
          value={status}
          onChange={(v) => {
            setStatus(v as ErrorStatus | 'all')
            setPage(1)
          }}
          data={[
            { value: 'open', label: t(`Offen (${data?.counts.open ?? 0})`, `Open (${data?.counts.open ?? 0})`) },
            {
              value: 'resolved',
              label: t(`Behoben (${data?.counts.resolved ?? 0})`, `Resolved (${data?.counts.resolved ?? 0})`),
            },
            { value: 'all', label: t('Alle', 'All') },
          ]}
        />
        <div style={{ flex: '1 1 320px', minWidth: 0 }}>
          <FilterBar
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder={t('Typ, Meldung, Route, Datei', 'Type, message, route, file')}
            groups={[
              {
                key: 'build',
                label: t('Version', 'Build'),
                value: build ?? '',
                defaultValue: '',
                kind: 'select',
                options: [{ value: '', label: t('Alle Versionen', 'All builds') }, ...buildOptions],
                onChange: (v) => {
                  setBuild(v || null)
                  setPage(1)
                },
              },
              {
                key: 'sort',
                label: t('Sortierung', 'Sort'),
                value: sort,
                defaultValue: 'last_seen',
                sort: true,
                options: [
                  { value: 'last_seen', label: t('Zuletzt aufgetreten', 'Last seen') },
                  { value: 'count', label: t('Am häufigsten', 'Most often') },
                  { value: 'first_seen', label: t('Neueste zuerst', 'Newest first') },
                ],
                onChange: (v) => {
                  setSort(v as Sort)
                  setPage(1)
                },
              },
            ]}
          />
        </div>
      </Group>

      {query.isError && <Text c="red">{failureText(query.error)}</Text>}

      <Paper withBorder p="md">
        <Title order={4} mb="sm">
          {t('Fehlergruppen', 'Error groups')}
        </Title>
        {data && data.errors.length === 0 ? (
          <Text c="dimmed" size="sm">
            {status === 'open' && !q && !build
              ? t('Keine offenen Fehler.', 'No open errors.')
              : t('Nichts gefunden.', 'Nothing found.')}
          </Text>
        ) : (
          <>
            <Table.ScrollContainer minWidth={680}>
              <Table highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('Fehler', 'Error')}</Table.Th>
                    <Table.Th w={80} ta="right">
                      {t('Anzahl', 'Count')}
                    </Table.Th>
                    <Table.Th w={170}>{t('Zuerst in', 'First in')}</Table.Th>
                    <Table.Th w={150}>{t('Zuletzt', 'Last seen')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data?.errors.map((g) => (
                    <ErrorRow key={g.id} group={g} canChange={canChange} onChanged={refresh} />
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
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
          </>
        )}
      </Paper>
    </Stack>
  )
}
