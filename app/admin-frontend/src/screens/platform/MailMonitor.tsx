import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  CloseButton,
  Code,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconAlertTriangle, IconPlugConnected, IconRefresh, IconSearch } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { Pagination, StatGrid, StatTile } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import {
  checkMailRelay,
  getMailRelayStatus,
  getMyAlerts,
  getPlatformEvents,
  resumeMainRelay,
  updateMyAlerts,
  type AlertType,
  type EventCategory,
  type EventLevel,
  type PlatformEvent,
  type RelayCheck,
  type RelaySummary,
} from '@/api/platform'
import { ALERT_TYPES, LEVEL_COLOR, categoryLabel, eventText, levelLabel } from './eventLabels'

const MONO = "'JetBrains Mono', monospace"

function failureText(err: unknown) {
  return err instanceof Error ? err.message : tr('Unbekannter Fehler', 'Unknown error')
}

function Dot({ ok }: { ok: boolean | null }) {
  const color = ok === null ? '#c2870f' : ok ? '#1f9d57' : '#c0392b'
  return (
    <span
      style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }}
    />
  )
}

const stepLabel = (step: string): string =>
  ({
    connect: tr('Verbinden', 'Connect'),
    ehlo: 'EHLO',
    starttls: 'STARTTLS',
    login: tr('Anmelden', 'Log in'),
  })[step] ?? step

function since(seconds: number) {
  return formatDateTime(new Date(seconds * 1000).toISOString())
}

// ── Outbound mail ────────────────────────────────────────────────────────────

function RelayCard({
  relay,
  checking,
  onCheck,
}: {
  relay: RelaySummary
  checking: boolean
  onCheck: () => void
}) {
  const check: RelayCheck | null = relay.last_check
  const title =
    relay.which === 'relay' ? tr('Haupt-Relay', 'Main relay') : tr('Fallback-Relay', 'Fallback relay')
  const state: boolean | null = !relay.configured ? null : check ? (check.down ? false : check.ok) : null

  return (
    <Paper withBorder shadow="sm" radius="lg" p="lg">
      <Group justify="space-between" mb={8} wrap="nowrap">
        <Group gap={10} wrap="nowrap">
          <Dot ok={state} />
          <Title order={4}>{title}</Title>
        </Group>
        {relay.configured && (
          <Button
            variant="default"
            size="xs"
            leftSection={<IconPlugConnected size={14} />}
            loading={checking}
            onClick={onCheck}
          >
            {tr('Jetzt prüfen', 'Check now')}
          </Button>
        )}
      </Group>

      {!relay.configured ? (
        <Text size="sm" c="dimmed">
          {relay.which === 'fallback'
            ? tr(
                'Kein Fallback eingerichtet. Unter Mail › Relay lässt sich eins hinterlegen.',
                'No fallback set up. Add one under Mail › Relay.',
              )
            : tr(
                'Kein Relay eingerichtet: Hubra kann keine Mails senden.',
                'No relay set up: Hubra cannot send mail.',
              )}
        </Text>
      ) : (
        <Stack gap={6}>
          <Text size="sm" ff={MONO} style={{ wordBreak: 'break-all' }}>
            {relay.host}:{relay.port}
            {relay.login ? '' : tr(' (ohne Anmeldung)', ' (no login)')}
          </Text>
          {!check && (
            <Text size="sm" c="dimmed">
              {tr('Noch nicht geprüft.', 'Not checked yet.')}
            </Text>
          )}
          {check && (
            <>
              <Text size="sm" fw={600} c={check.ok ? 'green.8' : 'red.8'}>
                {check.ok
                  ? tr(`OK, ${check.latency_ms} ms`, `OK, ${check.latency_ms} ms`)
                  : check.down
                    ? tr('Ausgefallen', 'Down')
                    : tr('Letzte Prüfung fehlgeschlagen', 'Last check failed')}
              </Text>
              {check.error && (
                <Text size="xs" c="red.8" style={{ wordBreak: 'break-word' }}>
                  {check.error}
                </Text>
              )}
              <Group gap={6} wrap="wrap">
                {check.steps.map((s) => (
                  <Badge
                    key={s.step}
                    variant="light"
                    color={s.ok ? 'green' : 'red'}
                    title={s.error ?? `${s.ms} ms`}
                  >
                    {stepLabel(s.step)}
                  </Badge>
                ))}
              </Group>
              <Text size="xs" c="dimmed">
                {check.scheduled
                  ? tr('Automatisch geprüft', 'Checked automatically')
                  : tr('Von Hand geprüft', 'Checked by hand')}{' '}
                {since(check.checked_at)}
              </Text>
            </>
          )}
        </Stack>
      )}
    </Paper>
  )
}


function cooldownText(email: string, minutes: number): string {
  const sentTo = tr(`Gehen an ${email}.`, `Sent to ${email}.`)
  if (minutes <= 0)
    return `${sentTo} ${tr('Jede Warnung kommt sofort.', 'Every alert comes right away.')}`
  const every =
    minutes % 60 === 0
      ? tr(
          minutes === 60 ? 'einmal pro Stunde' : `einmal alle ${minutes / 60} Stunden`,
          minutes === 60 ? 'once an hour' : `once every ${minutes / 60} hours`,
        )
      : tr(`einmal alle ${minutes} Minuten`, `once every ${minutes} minutes`)
  return `${sentTo} ${tr(
    `Jede Art kommt höchstens ${every}, ausser Ausfälle, Wiederherstellungen und Plugin-Neuigkeiten.`,
    `Each type comes at most ${every}, except outages, recoveries and plugin news.`,
  )}`
}

export function MyAlertsCard() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['my-platform-alerts'], queryFn: getMyAlerts })

  const toggle = async (id: AlertType, on: boolean) => {
    try {
      const alerts = await updateMyAlerts({ [id]: on })
      queryClient.setQueryData(['my-platform-alerts'], (old: typeof query.data) =>
        old ? { ...old, alerts } : old,
      )
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), failureText(err))
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg" p="lg">
      <Title order={4} mb={4}>
        {tr('Meine Warnungen per Mail', 'My alert mails')}
      </Title>
      <Text size="sm" c="dimmed" mb={12}>
        {query.data ? cooldownText(query.data.email, query.data.cooldownMinutes) : ' '}
      </Text>
      {query.data && !query.data.receives && (
        <Alert color="gray" variant="light" mb={12}>
          {tr(
            'Warnmails gehen nur an Plattform-Admins. Mit deiner Rolle siehst du die Warnungen hier, bekommst aber keine Mails.',
            'Alert mails only go to platform admins. With your role you see the alerts here but get no mail.',
          )}
        </Alert>
      )}
      {query.isError && <Text c="red">{failureText(query.error)}</Text>}
      {(['mail', 'platform'] as const).map((group) => (
        <Stack key={group} gap={12} mb={16}>
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">
            {group === 'mail' ? tr('Mail-Versand', 'Outbound mail') : tr('Plattform', 'Platform')}
          </Text>
          {ALERT_TYPES.filter((t) => t.group === group).map((t) => (
            <Switch
              key={t.id}
              checked={query.data?.alerts[t.id] ?? t.id !== 'plugin_updates'}
              disabled={!query.data}
              onChange={(e) => toggle(t.id, e.currentTarget.checked)}
              label={t.label()}
              description={t.desc()}
            />
          ))}
        </Stack>
      ))}
    </Paper>
  )
}

/** Outbound mail; "show in the log" opens the event log, filtered. */
export function OutboundMailTab() {
  const navigate = useNavigate()
  return (
    <OutboundMailPanel
      onShowLog={(lvl) =>
        navigate(`/app/platform/alerts/events${lvl ? `?level=${lvl}` : '?category=mail'}`)
      }
    />
  )
}

export function OutboundMailPanel({ onShowLog }: { onShowLog: (level?: EventLevel) => void }) {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const query = useQuery({
    queryKey: ['mail-relay'],
    queryFn: getMailRelayStatus,
    refetchInterval: 60_000,
  })
  const [checking, setChecking] = useState<string | null>(null)
  const data = query.data

  const check = async (which: 'relay' | 'fallback') => {
    setChecking(which)
    try {
      const [result] = await checkMailRelay(which)
      queryClient.invalidateQueries({ queryKey: ['mail-relay'] })
      if (result && result.ok === false) {
        notify('error', tr('Prüfung fehlgeschlagen', 'Check failed'), result.error)
      }
    } catch (err) {
      notify('error', tr('Prüfung fehlgeschlagen', 'Check failed'), failureText(err))
    } finally {
      setChecking(null)
    }
  }

  const resume = async () => {
    try {
      await resumeMainRelay()
      queryClient.invalidateQueries({ queryKey: ['mail-relay'] })
      notify('success', tr('Haupt-Relay wieder aktiv', 'Main relay back in use'))
    } catch (err) {
      notify('error', tr('Fehlgeschlagen', 'Failed'), failureText(err))
    }
  }

  return (
    <Stack gap={16}>
      <Group justify="space-between" wrap="wrap">
        <Text c="dimmed" size="sm" maw={720}>
          {tr(
            `Hubra meldet sich alle ${data?.check_every_minutes ?? 5} Minuten bei beiden Relays an, ohne etwas zu senden. Jede gesendete und jede fehlgeschlagene Mail steht im Ereignisprotokoll.`,
            `Hubra logs in to both relays every ${data?.check_every_minutes ?? 5} minutes, without sending anything. Every sent and every failed mail is in the event log.`,
          )}
        </Text>
        <Button
          variant="default"
          leftSection={<IconRefresh size={16} />}
          onClick={() => query.refetch()}
          loading={query.isFetching}
        >
          {tr('Aktualisieren', 'Refresh')}
        </Button>
      </Group>

      {query.isError && <Text c="red">{failureText(query.error)}</Text>}

      {data?.primary_down.active && (
        <Alert color="orange" icon={<IconAlertTriangle size={18} />}>
          <Group justify="space-between" wrap="wrap" gap={8}>
            <Text size="sm">
              {tr(
                `Das Haupt-Relay hat zuletzt Mails abgelehnt. Mails gehen noch ${Math.ceil(data.primary_down.seconds_left / 60)} Minuten über das Fallback.`,
                `The main relay refused mail recently. Mail goes through the fallback for ${Math.ceil(data.primary_down.seconds_left / 60)} more minutes.`,
              )}
            </Text>
            {canChange && (
              <Button size="xs" variant="white" color="orange" onClick={resume}>
                {tr('Haupt-Relay jetzt wieder nutzen', 'Use the main relay again now')}
              </Button>
            )}
          </Group>
        </Alert>
      )}

      {data && (
        <StatGrid columns={3} style={{ marginBottom: 0 }}>
          <StatTile
            label={tr('Gesendet (24 h)', 'Sent (24 h)')}
            value={data.stats.sent}
            onClick={() => onShowLog()}
          />
          <StatTile
            label={tr('Über Fallback (24 h)', 'Via fallback (24 h)')}
            value={data.stats.fallback}
            accent={data.stats.fallback ? '#c2870f' : undefined}
            onClick={() => onShowLog('warning')}
          />
          <StatTile
            label={tr('Fehlgeschlagen (24 h)', 'Failed (24 h)')}
            value={data.stats.failed}
            accent={data.stats.failed ? '#c0392b' : undefined}
            onClick={() => onShowLog('error')}
          />
        </StatGrid>
      )}

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        {(data?.relays ?? []).map((r) => (
          <RelayCard
            key={r.which}
            relay={r}
            checking={checking === r.which}
            onCheck={() => check(r.which)}
          />
        ))}
      </SimpleGrid>

      <Text size="sm" c="dimmed">
        {tr(
          'Welche Warnungen du per Mail bekommst, stellst du unter Warnungen › Meine Warnungen ein.',
          'Choose which alerts you get by mail under Alerts › My alerts.',
        )}
      </Text>
    </Stack>
  )
}

// ── Event log ────────────────────────────────────────────────────────────────

function EventDetails({ event }: { event: PlatformEvent }) {
  const entries = Object.entries(event.details).filter(([k]) => k !== 'steps')
  if (entries.length === 0) return null
  return (
    <Stack gap={2} mt={4}>
      {entries.map(([k, v]) => (
        <Text key={k} size="xs" c="dimmed" style={{ wordBreak: 'break-word' }}>
          <Code>{k}</Code> {Array.isArray(v) ? v.join(' · ') : String(v)}
        </Text>
      ))}
    </Stack>
  )
}

export function EventLogPanel({
  initialCategory,
  initialLevel,
  club,
  onClearClub,
}: {
  initialCategory?: EventCategory
  initialLevel?: EventLevel | 'problems'
  /** Only this club's events (from manage › Alle Vereine). */
  club?: { id: number; name: string }
  onClearClub?: () => void
}) {
  const [category, setCategory] = useState<EventCategory | ''>(
    initialCategory ?? (initialLevel && !club ? 'mail' : ''),
  )
  const [level, setLevel] = useState<EventLevel | 'problems' | ''>(initialLevel ?? '')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [open, setOpen] = useState<number | null>(null)

  const query = useQuery({
    queryKey: ['platform-events', category, level, club?.id, search, page, perPage],
    queryFn: () =>
      getPlatformEvents({
        category,
        level,
        tenant_id: club?.id,
        q: search.trim(),
        page,
        per_page: perPage,
      }),
  })
  const entries = query.data?.entries ?? []
  const total = query.data?.total ?? 0
  const pager = {
    page,
    perPage,
    total,
    totalPages: Math.max(1, Math.ceil(total / perPage)),
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
          `Was der Plattform passiert ist: jede gesendete und fehlgeschlagene Mail, Ausfälle von Relays und Diensten, fehlgeschlagene und gelöschte Backups, Plugin-Neuigkeiten, Systemwarnungen und die Warnungen an Plattform-Admins. Einträge bleiben ${query.data?.retention_days ?? 30} Tage. Was Personen geändert haben, steht im Audit-Log.`,
          `What happened to the platform: every sent and failed mail, relay and service outages, failed and deleted backups, plugin news, system alerts and the alerts to platform admins. Entries are kept for ${query.data?.retention_days ?? 30} days. What people changed is in the audit log.`,
        )}
      </Text>
      <Group gap="xs" wrap="wrap">
        {club && (
          <Badge
            size="lg"
            variant="light"
            rightSection={
              onClearClub ? (
                <CloseButton
                  size="xs"
                  aria-label={tr('Vereinsfilter entfernen', 'Remove club filter')}
                  onClick={onClearClub}
                />
              ) : undefined
            }
          >
            {tr('Verein', 'Club')}: {club.name}
          </Badge>
        )}
        <TextInput
          leftSection={<IconSearch size={16} />}
          placeholder={tr('Adresse oder Betreff', 'Address or subject')}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value)
            setPage(1)
          }}
          w={240}
        />
        {(['', 'mail', 'relay', 'service', 'backup', 'plugin', 'system', 'alert'] as const).map((c) => (
          <Button
            key={c || 'all'}
            size="xs"
            variant={category === c ? 'filled' : 'default'}
            onClick={() => {
              setCategory(c)
              setPage(1)
            }}
          >
            {c ? categoryLabel(c) : tr('Alle', 'All')}
          </Button>
        ))}
        <span style={{ width: 8 }} />
        {(['', 'problems', 'warning', 'error'] as const).map((l) => (
          <Button
            key={l || 'any'}
            size="xs"
            variant={level === l ? 'filled' : 'default'}
            color={l && l !== 'problems' ? LEVEL_COLOR[l] : undefined}
            onClick={() => {
              setLevel(l)
              setPage(1)
            }}
          >
            {l === 'problems'
              ? tr('Warnungen und Fehler', 'Warnings and errors')
              : l
                ? levelLabel(l)
                : tr('Jede Stufe', 'Any level')}
          </Button>
        ))}
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

      {query.isError && <Text c="red">{failureText(query.error)}</Text>}

      <Paper withBorder shadow="sm" radius="lg">
        <Pagination {...pager} />
        <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={150}>{tr('Zeit', 'Time')}</Table.Th>
                <Table.Th w={110}>{tr('Stufe', 'Level')}</Table.Th>
                <Table.Th w={90}>{tr('Art', 'Type')}</Table.Th>
                <Table.Th>{tr('Ereignis', 'Event')}</Table.Th>
                <Table.Th w={140}>{tr('Verein', 'Club')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {!query.isLoading && entries.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text c="dimmed" size="sm">
                      {tr('Keine Einträge.', 'No entries.')}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              )}
              {entries.map((e) => (
                <Table.Tr
                  key={e.id}
                  style={{ cursor: 'pointer', verticalAlign: 'top' }}
                  onClick={() => setOpen(open === e.id ? null : e.id)}
                >
                  <Table.Td fz="sm" c="dimmed">
                    {formatDateTime(e.time)}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={LEVEL_COLOR[e.level]} size="sm">
                      {levelLabel(e.level)}
                    </Badge>
                  </Table.Td>
                  <Table.Td fz="sm">{categoryLabel(e.category)}</Table.Td>
                  <Table.Td>
                    <Text size="sm" style={{ wordBreak: 'break-word' }}>
                      {eventText(e)}
                    </Text>
                    {open === e.id && <EventDetails event={e} />}
                  </Table.Td>
                  <Table.Td fz="sm">{e.club ?? '–'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        <Pagination {...pager} />
      </Paper>
    </Stack>
  )
}
