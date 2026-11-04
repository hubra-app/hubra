import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Anchor,
  Badge,
  Button,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { IconBrandDiscord, IconSearch } from '@tabler/icons-react'
import { EmptyState, SlideOver, StatGrid, StatTile } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import {
  getDiscordClubActivity,
  getDiscordClubs,
  type DiscordBotEvent,
  type DiscordClubServer,
} from '@/api/platform'

const MONO = "'JetBrains Mono', monospace"
const when = (iso?: string | null) => (iso ? formatDateTime(iso) : '—')

type Filter = 'all' | 'problems' | 'pending'

/** What a bot log action means, as the club page shows it. */
const ACTION_LABEL: Record<string, [string, string]> = {
  announced: ['Gepostet', 'Posted'],
  skipped: ['Nicht gepostet', 'Not posted'],
  updated: ['Aktualisiert', 'Updated'],
  roles: ['Rollen', 'Roles'],
  events: ['Discord-Events', 'Discord events'],
  profile: ['Bot-Profil', 'Bot profile'],
  joined: ['Beigetreten', 'Joined'],
  dm: ['Direktnachricht', 'Direct message'],
  registration: ['Anmeldung', 'Sign-up'],
  voted: ['Abstimmung', 'Vote'],
  attendance: ['Anwesenheit', 'Attendance'],
  command: ['Befehl', 'Command'],
  channels: ['Kanäle', 'Channels'],
  test: ['Test', 'Test'],
  changed: ['Einstellungen', 'Settings'],
  connected: ['Verbunden', 'Connected'],
}

function actionLabel(action: string) {
  const found = ACTION_LABEL[action]
  return found ? tr(found[0], found[1]) : action
}

function problemOf(s: DiscordClubServer): string | null {
  if (s.botOnServer === false) return tr('Bot nicht mehr auf dem Server', 'Bot no longer on the server')
  if (s.status === 'active' && s.scopes.includes('announce') && !s.mainChannel)
    return tr('Kein Hauptkanal gewählt', 'No main channel picked')
  if (s.week.failed) return tr(`${s.week.failed} Fehler`, `${s.week.failed} errors`)
  return null
}

function BotLog({ server, onClose }: { server: DiscordClubServer; onClose: () => void }) {
  const [errorsOnly, setErrorsOnly] = useState(false)
  const query = useQuery({
    queryKey: ['discord-club-activity', server.id],
    queryFn: () => getDiscordClubActivity(server.id),
  })
  const events: DiscordBotEvent[] = (query.data?.events ?? []).filter((e) => !errorsOnly || !e.ok)
  return (
    <SlideOver
      title={server.club}
      subtitle={`${server.server} · ${tr('Bot-Protokoll', 'Bot log')}`}
      icon={<IconBrandDiscord size={18} />}
      width={520}
      onClose={onClose}
    >
      <Stack gap="sm">
        <SegmentedControl
          size="xs"
          value={errorsOnly ? 'errors' : 'all'}
          onChange={(v) => setErrorsOnly(v === 'errors')}
          data={[
            { value: 'all', label: tr('Alles', 'Everything') },
            { value: 'errors', label: tr('Nur Fehler', 'Errors only') },
          ]}
        />
        {query.isLoading && <Text c="dimmed">{tr('Wird geladen …', 'Loading…')}</Text>}
        {query.isError && (
          <Text c="red" size="sm">
            {(query.error as Error).message}
          </Text>
        )}
        {query.data && events.length === 0 && (
          <EmptyState title={tr('Noch nichts protokolliert.', 'Nothing logged yet.')} />
        )}
        {events.map((e, i) => (
          <Paper key={i} withBorder p="xs">
            <Group justify="space-between" gap={6} wrap="nowrap">
              <Badge size="sm" variant="light" color={e.ok ? (e.action === 'skipped' ? 'gray' : 'green') : 'red'}>
                {actionLabel(e.action)}
              </Badge>
              <Text size="xs" c="dimmed">
                {when(e.at)}
              </Text>
            </Group>
            {e.detail && (
              <Text size="sm" mt={4} style={{ wordBreak: 'break-word' }}>
                {e.detail}
              </Text>
            )}
          </Paper>
        ))}
      </Stack>
    </SlideOver>
  )
}

/** Manage › Discord › Vereinsserver: every club's bot at a glance. */
export function DiscordClubsPanel() {
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['discord-clubs'], queryFn: getDiscordClubs })
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [open, setOpen] = useState<DiscordClubServer | null>(null)

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (query.data?.servers ?? []).filter((s) => {
      if (q && !`${s.club} ${s.server} ${s.serverId}`.toLowerCase().includes(q)) return false
      if (filter === 'problems') return problemOf(s) !== null || !!s.lastError
      if (filter === 'pending') return s.status === 'pending'
      return true
    })
  }, [query.data, search, filter])

  if (query.isLoading) return <Text c="dimmed">{tr('Wird geladen …', 'Loading…')}</Text>
  if (query.isError || !query.data)
    return <Text c="red">{query.error instanceof Error ? query.error.message : tr('Unbekannter Fehler', 'Unknown error')}</Text>
  const d = query.data

  return (
    <Stack gap={16}>
      <StatGrid columns={4} style={{ marginBottom: 0 }}>
        <StatTile label={tr('Server', 'Servers')} value={d.totals.servers} sub={tr(`${d.totals.active} aktiv`, `${d.totals.active} active`)} />
        <StatTile
          label={tr(`Mit Fehlern (${d.days} Tage)`, `With errors (${d.days} days)`)}
          value={d.totals.withErrors}
          accent={d.totals.withErrors ? 'var(--mantine-color-red-text)' : undefined}
          onClick={() => setFilter('problems')}
        />
        <StatTile
          label={tr('Bot fehlt', 'Bot missing')}
          value={d.totals.botMissing}
          sub={d.checkedAt ? `${tr('Geprüft', 'Checked')} ${when(d.checkedAt)}` : tr('Noch nicht geprüft', 'Not checked yet')}
          accent={d.totals.botMissing ? 'var(--mantine-color-orange-text)' : undefined}
        />
        <StatTile
          label={tr('Discord-Plugin', 'Discord plugin')}
          value={d.plugin.installed ? d.plugin.version ?? '–' : tr('Fehlt', 'Missing')}
          accent={d.plugin.installed ? undefined : 'var(--mantine-color-red-text)'}
        />
      </StatGrid>

      <Paper withBorder p="lg">
        <Group justify="space-between" wrap="wrap" gap="sm" mb="sm">
          <TextInput
            leftSection={<IconSearch size={14} />}
            placeholder={tr('Verein oder Server suchen', 'Search club or server')}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            style={{ flex: '1 1 220px', maxWidth: 360 }}
          />
          <SegmentedControl
            size="xs"
            value={filter}
            onChange={(v) => setFilter(v as Filter)}
            data={[
              { value: 'all', label: tr('Alle', 'All') },
              { value: 'problems', label: tr('Mit Problemen', 'With problems') },
              { value: 'pending', label: tr('Wartet auf Bestätigung', 'Waiting for approval') },
            ]}
          />
        </Group>
        {shown.length === 0 ? (
          <EmptyState
            title={
              d.servers.length === 0
                ? tr('Noch kein Verein hat Discord verbunden.', 'No club has connected Discord yet.')
                : tr('Kein Server passt zum Filter.', 'No server matches the filter.')
            }
          />
        ) : (
          <Table.ScrollContainer minWidth={860}>
            <Table verticalSpacing="sm" fz="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{tr('Verein', 'Club')}</Table.Th>
                  <Table.Th>Server</Table.Th>
                  <Table.Th>{tr('Eingeschaltet', 'Turned on')}</Table.Th>
                  <Table.Th>{tr(`${d.days} Tage`, `${d.days} days`)}</Table.Th>
                  <Table.Th>{tr('Letzte Ankündigung', 'Last announcement')}</Table.Th>
                  <Table.Th>{tr('Zustand', 'State')}</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {shown.map((s) => {
                  const problem = problemOf(s)
                  return (
                    <Table.Tr key={s.id}>
                      <Table.Td>
                        <Anchor size="sm" onClick={() => navigate(`/app/tenants/${s.clubId}`)}>
                          {s.club}
                        </Anchor>
                        {!s.clubActive && (
                          <Text size="xs" c="dimmed">
                            {tr('Verein nicht aktiv', 'Club not active')}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        {s.server}
                        <Text size="xs" c="dimmed" ff={MONO}>
                          {s.serverId}
                        </Text>
                      </Table.Td>
                      <Table.Td style={{ maxWidth: 260 }}>
                        <Group gap={4}>
                          {s.features.length === 0 ? (
                            <Text size="xs" c="dimmed">
                              —
                            </Text>
                          ) : (
                            s.features.map((f) => (
                              <Badge key={f} size="xs" variant="light" color="gray">
                                {f}
                              </Badge>
                            ))
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{tr(`${s.week.ok} ok`, `${s.week.ok} ok`)}</Text>
                        {s.week.failed > 0 && (
                          <Text size="xs" c="red.8">
                            {tr(`${s.week.failed} Fehler`, `${s.week.failed} failed`)}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>{when(s.lastPostAt)}</Table.Td>
                      <Table.Td style={{ maxWidth: 240 }}>
                        <Group gap={4}>
                          {s.status === 'pending' ? (
                            <Badge size="sm" variant="light" color="gray">
                              {tr('Wartet', 'Pending')}
                            </Badge>
                          ) : problem ? (
                            <Badge size="sm" variant="light" color="red">
                              {problem}
                            </Badge>
                          ) : (
                            <Badge size="sm" variant="light" color="green">
                              {tr('Läuft', 'Running')}
                            </Badge>
                          )}
                        </Group>
                        {s.lastError && (
                          <Text size="xs" c="red.8" mt={2} lineClamp={2} title={s.lastError}>
                            {when(s.lastErrorAt)}: {s.lastError}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Button size="xs" variant="default" onClick={() => setOpen(s)}>
                          {tr('Protokoll', 'Log')}
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>
      {open && <BotLog server={open} onClose={() => setOpen(null)} />}
    </Stack>
  )
}
