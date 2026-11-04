import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, Stack, Table, Text, Tooltip } from '@mantine/core'
import { IconPlayerStop, IconRefresh } from '@tabler/icons-react'
import { formatDateTime } from '@/format'
import { Pagination } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { useLang } from '@/lang'
import {
  endSupportSession,
  listSupportSessions,
  type SupportPerson,
  type SupportSession,
} from '@/api/tenants'

const STATUS_COLOR: Record<SupportSession['status'], string> = {
  active: 'orange',
  ended: 'gray',
  expired: 'gray',
  revoked: 'red',
}

function duration(seconds: number, tr: (de: string, en: string) => string) {
  const min = Math.max(0, Math.round(seconds / 60))
  if (min < 60) return tr(`${min} Min.`, `${min} min`)
  const h = Math.floor(min / 60)
  const rest = min % 60
  return rest ? tr(`${h} Std. ${rest} Min.`, `${h} h ${rest} min`) : tr(`${h} Std.`, `${h} h`)
}

function Person({ p }: { p: SupportPerson | null }) {
  if (!p) return <Text c="dimmed" fz="sm">–</Text>
  return (
    <div style={{ minWidth: 0 }}>
      <Text fz="sm" fw={500} truncate>
        {p.name || p.email}
      </Text>
      {p.name && (
        <Text fz="xs" c="dimmed" truncate>
          {p.email}
        </Text>
      )}
    </div>
  )
}

/** The impersonation log: every support session, with ending running ones. */
export function SupportSessionsTab() {
  const { tr } = useLang()
  const { hasGlobalPermission, notify } = useAdmin()
  const canEnd = hasGlobalPermission('impersonate')
  const queryClient = useQueryClient()
  const [onlyActive, setOnlyActive] = useState(false)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [ending, setEnding] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['support-sessions', onlyActive, page, perPage],
    queryFn: () =>
      listSupportSessions({ status: onlyActive ? 'active' : undefined, page, per_page: perPage }),
    refetchInterval: 30_000,
  })
  const sessions = query.data?.sessions ?? []
  const total = query.data?.total ?? 0

  const statusText = (s: SupportSession) =>
    ({
      active: tr(`läuft bis ${formatDateTime(s.expires_at).slice(-5)}`, `running until ${formatDateTime(s.expires_at).slice(-5)}`),
      ended: tr('beendet', 'ended'),
      expired: tr('abgelaufen', 'timed out'),
      revoked: s.ended_by
        ? tr(`beendet von ${s.ended_by.name || s.ended_by.email}`, `ended by ${s.ended_by.name || s.ended_by.email}`)
        : tr('vorzeitig beendet', 'ended early'),
    })[s.status]

  const end = async (s: SupportSession) => {
    if (!s.session) return
    setEnding(s.session)
    try {
      await endSupportSession(s.session)
      notify('success', tr('Support-Sitzung beendet', 'Support session ended'), s.club ?? undefined)
      await queryClient.invalidateQueries({ queryKey: ['support-sessions'] })
    } catch (err) {
      notify('error', tr('Beenden fehlgeschlagen', 'Could not end it'), err instanceof Error ? err.message : undefined)
    } finally {
      setEnding(null)
    }
  }

  return (
    <Stack gap="md">
      <Group gap="xs" wrap="wrap">
        <Button
          size="xs"
          variant={!onlyActive ? 'filled' : 'default'}
          onClick={() => {
            setOnlyActive(false)
            setPage(1)
          }}
        >
          {tr('Alle', 'All')}
        </Button>
        <Button
          size="xs"
          color="orange"
          variant={onlyActive ? 'filled' : 'default'}
          onClick={() => {
            setOnlyActive(true)
            setPage(1)
          }}
        >
          {tr('Laufen gerade', 'Running now')}
          {query.data ? ` · ${query.data.active}` : ''}
        </Button>
        <Button
          variant="subtle"
          size="xs"
          ml="auto"
          leftSection={<IconRefresh size={14} />}
          onClick={() => query.refetch()}
          loading={query.isFetching}
        >
          {tr('Aktualisieren', 'Refresh')}
        </Button>
      </Group>

      <Paper withBorder style={{ overflow: 'hidden' }}>
        {!query.isLoading && sessions.length === 0 ? (
          <Text p={40} ta="center" c="dimmed">
            {onlyActive
              ? tr('Gerade läuft keine Support-Sitzung.', 'No support session is running.')
              : tr('Noch keine Support-Zugriffe.', 'No support access yet.')}
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={900}>
            <Table highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={150}>{tr('Beginn', 'Started')}</Table.Th>
                  <Table.Th>{tr('Wer', 'Who')}</Table.Th>
                  <Table.Th>{tr('Verein und Mitglied', 'Club and member')}</Table.Th>
                  <Table.Th>{tr('Grund', 'Reason')}</Table.Th>
                  <Table.Th w={110}>{tr('Zugriff', 'Access')}</Table.Th>
                  <Table.Th w={200}>{tr('Dauer', 'Length')}</Table.Th>
                  <Table.Th w={120} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sessions.map((s) => (
                  <Table.Tr key={s.id} style={{ verticalAlign: 'top' }}>
                    <Table.Td fz="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                      {formatDateTime(s.started_at)}
                    </Table.Td>
                    <Table.Td>
                      <Person p={s.staff} />
                    </Table.Td>
                    <Table.Td>
                      <Text fz="sm" fw={600}>
                        {s.club ?? '–'}
                      </Text>
                      <Text fz="xs" c="dimmed">
                        {s.member ? s.member.name || s.member.email : tr(`Mitglied #${s.member_id}`, `Member #${s.member_id}`)}
                      </Text>
                    </Table.Td>
                    <Table.Td fz="sm" style={{ wordBreak: 'break-word' }}>
                      {s.reason || '–'}
                    </Table.Td>
                    <Table.Td>
                      <Badge size="sm" variant="light" color={s.mode === 'act' ? 'red' : 'acc'}>
                        {s.mode === 'act' ? tr('Ändern', 'Changes') : tr('Nur ansehen', 'Look only')}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text fz="sm">
                        {duration(s.seconds, tr)}
                        <Text span fz="xs" c="dimmed">
                          {' '}
                          / {duration(s.minutes * 60, tr)}
                        </Text>
                      </Text>
                      <Badge size="sm" variant="light" color={STATUS_COLOR[s.status]} mt={4}>
                        {statusText(s)}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      {s.status === 'active' && canEnd && s.session && (
                        <Tooltip label={tr('Die Sitzung endet bei der nächsten Anfrage', 'The session ends with its next request')} withArrow>
                          <Button
                            size="xs"
                            color="red"
                            variant="light"
                            leftSection={<IconPlayerStop size={14} />}
                            loading={ending === s.session}
                            onClick={() => end(s)}
                          >
                            {tr('Beenden', 'End')}
                          </Button>
                        </Tooltip>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        <Pagination
          page={page}
          perPage={perPage}
          total={total}
          totalPages={Math.max(1, Math.ceil(total / perPage))}
          goPage={setPage}
          setPerPage={(n) => {
            setPerPage(n)
            setPage(1)
          }}
        />
      </Paper>
    </Stack>
  )
}
