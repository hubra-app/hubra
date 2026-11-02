import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Alert, Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import {
  IconAlertTriangle,
  IconChevronRight,
  IconCircleCheck,
  IconRefresh,
} from '@tabler/icons-react'
import { PageHead, StatGrid, StatTile, Tabs } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr, useLang } from '@/lang'
import { getAlertsOverview, type EventCategory, type OpenProblem } from '@/api/platform'
import { EventLogPanel, MyAlertsCard } from './MailMonitor'
import { AlertRulesPanel, MaintenanceCard } from './AlertControls'
import { MaintenanceWindowsCard } from './MaintenanceWindows'
import { PerformancePanel } from './Performance'
import { LEVEL_COLOR, categoryLabel, eventText, levelLabel } from './eventLabels'

// The server names problems in English; the known ones are told here.
function problemTitle(p: OpenProblem): string {
  const [kind, which] = p.id.split(':')
  const service =
    which === 'db' ? tr('Datenbank', 'Database') : which === 'redis' ? 'Redis' : 'IMAP'
  switch (kind) {
    case 'jobs':
      return tr('Hintergrundaufgaben laufen nicht', p.title)
    case 'service':
      return tr(`${service} antwortet nicht`, p.title)
    case 'relay':
      if (which === 'skipped') return tr('Mails gehen über das Fallback-Relay', p.title)
      return tr(
        which === 'fallback' ? 'Fallback-Relay ausgefallen' : 'Haupt-Relay ausgefallen',
        p.title,
      )
    case 'mail':
      return tr(
        p.title.replace(
          /^(\d+) mails not delivered in 24 hours$/,
          '$1 Mails in 24 Stunden nicht zugestellt',
        ),
        p.title,
      )
    case 'perf':
      return which === 'slow'
        ? tr(
            p.title.replace(
              /^API is slow: p95 (\d+) ms in the last hour$/,
              'API ist langsam: p95 $1 ms in der letzten Stunde',
            ),
            p.title,
          )
        : tr(
            p.title.replace(
              /^(\d+) server errors in the last hour$/,
              '$1 Serverfehler in der letzten Stunde',
            ),
            p.title,
          )
    case 'backup':
      return which === 'none'
        ? tr('Seit 2 Tagen kein erfolgreiches geplantes Backup', p.title)
        : tr(
            p.title.replace(
              'Last scheduled backup failed for',
              'Letztes geplantes Backup fehlgeschlagen:',
            ),
            p.title,
          )
    case 'discord':
      return which === 'bot'
        ? tr('Der Discord-Bot kann sich nicht anmelden', p.title)
        : which === 'channel'
          ? tr('Der Bot sieht den Kanal des Plattform-Logs nicht', p.title)
          : tr('Meldungen ins Plattform-Log auf Discord schlagen fehl', p.title)
    default:
      return p.title
  }
}

function problemDetail(p: OpenProblem): string {
  if (p.id === 'jobs')
    return tr(
      'Celery-Beat oder der Worker hat seit über einer Minute keine Prüfung gemacht: Relay-Prüfungen, Backups, Erinnerungen und Warnmails stehen still. Das kann Hubra nicht selbst per Mail melden; eine Überwachung von aussen (z. B. auf /health) sieht es.',
      `${p.detail} Hubra cannot mail this itself; an outside monitor (e.g. on /health) sees it.`,
    )
  if (p.id === 'mail:failed')
    return tr(
      'Abgelehnte Adressen zählen mit; das Ereignisprotokoll zeigt jede einzelne.',
      p.detail,
    )
  if (p.id === 'backup:none') return tr('Backups laufen täglich um 03:00 UTC.', p.detail)
  if (p.id === 'perf:slow' || p.id === 'perf:errors')
    return tr('Der Tab «Leistung» zeigt, welche Routen langsam sind oder Fehler liefern.', p.detail)
  return p.detail
}

function ProblemRow({ p }: { p: OpenProblem }) {
  const navigate = useNavigate()
  return (
    <Paper
      withBorder
      radius="md"
      p="md"
      style={{
        borderLeft: `4px solid var(--mantine-color-${p.level === 'error' ? 'red' : 'orange'}-6)`,
        cursor: p.link ? 'pointer' : undefined,
      }}
      onClick={() => p.link && navigate(p.link)}
    >
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <div style={{ minWidth: 0 }}>
          <Group gap={8} mb={4} wrap="wrap">
            <Badge variant="light" color={LEVEL_COLOR[p.level]} size="sm">
              {levelLabel(p.level)}
            </Badge>
            <Text size="xs" c="dimmed">
              {categoryLabel(p.area)}
              {p.since
                ? ` · ${tr('seit', 'since')} ${formatDateTime(new Date(p.since * 1000).toISOString())}`
                : ''}
            </Text>
          </Group>
          <Text fw={600} size="sm">
            {problemTitle(p)}
          </Text>
          {problemDetail(p) && (
            <Text size="sm" c="dimmed" style={{ wordBreak: 'break-word' }}>
              {problemDetail(p)}
            </Text>
          )}
        </div>
        {p.link && <IconChevronRight size={18} style={{ flexShrink: 0, opacity: 0.5 }} />}
      </Group>
    </Paper>
  )
}

const AREAS: EventCategory[] = ['mail', 'service', 'backup', 'system']

function OverviewPanel() {
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: ['alerts-overview'],
    queryFn: getAlertsOverview,
    refetchInterval: 60_000,
  })
  const data = query.data
  const problems = data?.problems ?? []

  return (
    <Stack gap={16}>
      <Group justify="space-between" wrap="wrap">
        <Text c="dimmed" size="sm" maw={720}>
          {tr(
            'Was gerade nicht stimmt, die letzten Warnungen und wie viele Warnungen und Fehler es in den letzten 24 Stunden gab.',
            'What is wrong right now, the latest alerts and how many warnings and errors the last 24 hours had.',
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
      {query.isError && (
        <Text c="red">{query.error instanceof Error ? query.error.message : ''}</Text>
      )}

      <MaintenanceCard state={data?.maintenance} />

      <MaintenanceWindowsCard />

      {data && !data.switches.enabled && !data.maintenance.active && (
        <Alert color="orange" variant="light">
          <Group justify="space-between" wrap="wrap">
            <Text size="sm">
              {tr(
                'Warnungen sind ausgeschaltet: Es geht nichts per Mail oder auf Discord raus.',
                'Alerts are switched off: nothing goes out by mail or to Discord.',
              )}
            </Text>
            <Button
              size="compact-sm"
              variant="light"
              color="orange"
              onClick={() => navigate('/app/platform/alerts/rules')}
            >
              {tr('Benachrichtigungen', 'Notifications')}
            </Button>
          </Group>
        </Alert>
      )}

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group gap={10} mb={12}>
          {data && problems.length === 0 ? (
            <IconCircleCheck size={22} color="var(--mantine-color-green-7)" />
          ) : (
            <IconAlertTriangle size={22} color="var(--mantine-color-orange-7)" />
          )}
          <Title order={4}>
            {!data
              ? tr('Offene Probleme', 'Open problems')
              : problems.length === 0
                ? tr('Alles in Ordnung', 'All clear')
                : tr(`${problems.length} offene Probleme`, `${problems.length} open problems`)}
          </Title>
        </Group>
        {data && problems.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr(
              'Dienste, Relays, Hintergrundaufgaben und Backups laufen.',
              'Services, relays, background jobs and backups are running.',
            )}
          </Text>
        )}
        <Stack gap={10}>
          {problems.map((p) => (
            <ProblemRow key={p.id} p={p} />
          ))}
        </Stack>
      </Paper>

      {data && (
        <StatGrid columns={4} style={{ marginBottom: 0 }}>
          {AREAS.map((area) => {
            const c = data.counts[area] ?? { warning: 0, error: 0 }
            return (
              <StatTile
                key={area}
                label={`${categoryLabel(area)} (24 h)`}
                value={c.error + c.warning}
                sub={tr(
                  `${c.error} Fehler, ${c.warning} Warnungen`,
                  `${c.error} errors, ${c.warning} warnings`,
                )}
                accent={c.error ? '#c0392b' : c.warning ? '#c2870f' : undefined}
                onClick={() => navigate(`/app/platform/alerts/events?category=${area}`)}
              />
            )
          })}
        </StatGrid>
      )}

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group justify="space-between" mb={12}>
          <Title order={4}>{tr('Letzte Warnungen', 'Latest alerts')}</Title>
          <Button
            variant="subtle"
            size="compact-sm"
            onClick={() => navigate('/app/platform/alerts/events?category=alert')}
          >
            {tr('Alle', 'All')}
          </Button>
        </Group>
        {data && data.recent.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr('Noch keine Warnungen.', 'No alerts yet.')}
          </Text>
        )}
        <Stack gap={0}>
          {(data?.recent ?? []).map((e) => (
            <Group
              key={e.id}
              gap={12}
              wrap="nowrap"
              py={8}
              style={{ borderBottom: '1px solid var(--hb-border)' }}
            >
              <Badge
                variant="light"
                color={LEVEL_COLOR[e.level]}
                size="sm"
                style={{ flexShrink: 0 }}
              >
                {levelLabel(e.level)}
              </Badge>
              <Text size="sm" style={{ flex: 1, minWidth: 0, wordBreak: 'break-word' }}>
                {eventText(e)}
              </Text>
              <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                {formatDateTime(e.time)}
              </Text>
            </Group>
          ))}
        </Stack>
      </Paper>
    </Stack>
  )
}

const TABS = ['overview', 'performance', 'events', 'rules', 'settings'] as const
type Tab = (typeof TABS)[number]
const CATEGORIES = ['mail', 'relay', 'service', 'backup', 'plugin', 'system', 'alert']

/** Platform alerts for platform staff (platform.diagnostics): open problems,
 * the event log and which alert mails each admin gets. */
export function Alerts() {
  const { tr } = useLang()
  const location = useLocation()
  const navigate = useNavigate()
  const last = location.pathname.split('/').pop() as Tab
  const tab: Tab = TABS.includes(last) ? last : 'overview'
  const search = new URLSearchParams(location.search)
  const level = search.get('level')
  const category = search.get('category')
  const clubId = Number(search.get('club'))
  const club = clubId ? { id: clubId, name: search.get('name') ?? `#${clubId}` } : undefined

  return (
    <div>
      <PageHead
        title={tr('Warnungen', 'Alerts')}
        desc={tr(
          'Probleme der Plattform, wie schnell die API antwortet, das Ereignisprotokoll und welche Warnungen du per Mail bekommst.',
          'Problems on the platform, how fast the API answers, the event log and which alerts you get by mail.',
        )}
      />
      <Tabs
        tabs={[
          { id: 'overview', label: tr('Übersicht', 'Overview') },
          { id: 'performance', label: tr('Leistung', 'Performance') },
          { id: 'events', label: tr('Ereignisse', 'Event log') },
          { id: 'rules', label: tr('Benachrichtigungen', 'Notifications') },
          { id: 'settings', label: tr('Meine Warnungen', 'My alerts') },
        ]}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/platform/alerts/${id}`)}
      />
      {tab === 'overview' && <OverviewPanel />}
      {tab === 'performance' && <PerformancePanel />}
      {tab === 'events' && (
        <EventLogPanel
          key={location.search}
          initialLevel={
            level === 'warning' || level === 'error' || level === 'problems' ? level : undefined
          }
          club={club}
          onClearClub={() => navigate('/app/platform/alerts/events')}
          initialCategory={
            category && CATEGORIES.includes(category) ? (category as EventCategory) : undefined
          }
        />
      )}
      {tab === 'rules' && <AlertRulesPanel />}
      {tab === 'settings' && <MyAlertsCard />}
    </div>
  )
}
