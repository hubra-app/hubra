import { useQuery } from '@tanstack/react-query'
import { Alert, Anchor, Box, Group, Loader, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleX,
  IconTool,
} from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { BASE } from '@hubra/api-client'
import { AuthFrame } from '@/components/AuthFrame'
import { getLang, useLang } from '@/lang'

type Level = 'operational' | 'degraded' | 'down'
type Component = 'app' | 'mail' | 'notifications'

interface StatusPage {
  overall: Level | 'maintenance'
  components: { id: Component; level: Level }[]
  maintenance: {
    active: boolean
    message: string
    until: string | null
    upcoming: { starts_at: string; ends_at: string; message: string } | null
  }
  incidents: { component: Component; level: Level; started_at: string; ended_at: string | null }[]
  past_maintenance: { starts_at: string; ends_at: string; message: string }[]
  history_days: number
  checked_at: string
  club: { slug: string; name: string } | null
}

/** Public: no session, no refresh, works while the club API is in maintenance. */
async function getStatus(club: string | null): Promise<StatusPage> {
  const qs = club ? `?club=${encodeURIComponent(club)}` : ''
  const res = await fetch(`${BASE}/status${qs}`, { credentials: 'omit' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as StatusPage
}

function when(iso: string) {
  return new Date(iso).toLocaleString(getLang() === 'en' ? 'en-GB' : 'de-CH', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const COLOR: Record<Level | 'maintenance', string> = {
  operational: 'green',
  degraded: 'orange',
  down: 'red',
  maintenance: 'blue',
}

function LevelIcon({ level, size = 22 }: { level: Level | 'maintenance'; size?: number }) {
  const Icon =
    level === 'operational'
      ? IconCircleCheck
      : level === 'maintenance'
        ? IconTool
        : level === 'down'
          ? IconCircleX
          : IconAlertTriangle
  return <Icon size={size} color={`var(--mantine-color-${COLOR[level]}-text)`} aria-hidden />
}

/** sso › /status (?club=<slug>): is Hubra working, in plain words. */
export function StatusScreen() {
  const { tr } = useLang()
  const navigate = useNavigate()
  const club = new URLSearchParams(window.location.search).get('club')
  const query = useQuery({
    queryKey: ['status', club],
    queryFn: () => getStatus(club),
    refetchInterval: 60_000,
  })
  const data = query.data

  const name: Record<Component, string> = {
    app: tr('Vereins-App und Anmeldung', 'Club app and sign-in'),
    mail: tr('Mails an Mitglieder', 'Mail to members'),
    notifications: tr('Erinnerungen und Benachrichtigungen', 'Reminders and notifications'),
  }
  const levelText: Record<Level, string> = {
    operational: tr('Funktioniert', 'Working'),
    degraded: tr('Eingeschränkt', 'Limited'),
    down: tr('Ausgefallen', 'Down'),
  }
  const headline: Record<StatusPage['overall'], string> = {
    operational: tr('Alles funktioniert', 'Everything is working'),
    degraded: tr('Einzelne Teile sind eingeschränkt', 'Some parts are limited'),
    down: tr('Ein Teil von Hubra ist ausgefallen', 'Part of Hubra is down'),
    maintenance: tr('Wartung läuft', 'Maintenance in progress'),
  }
  const incidentText = (i: StatusPage['incidents'][number]) =>
    i.component === 'app'
      ? i.level === 'down'
        ? tr('Vereins-App nicht erreichbar', 'Club app unreachable')
        : tr('Vereins-App langsam oder teilweise gestört', 'Club app slow or partly disrupted')
      : tr('Mails verzögert', 'Mail delayed')

  return (
    <AuthFrame wide>
      <Title order={1} fz={30} mb={6}>
        {tr('Systemstatus', 'System status')}
      </Title>
      <Text c="dimmed" mb={24}>
        {data?.club
          ? tr(`Hubra für ${data.club.name}`, `Hubra for ${data.club.name}`)
          : tr('Funktioniert Hubra gerade?', 'Is Hubra working right now?')}
      </Text>

      {query.isLoading && (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      )}
      {query.isError && (
        <Alert color="red" variant="light" icon={<IconCircleX size={18} />}>
          {tr(
            'Der Status lässt sich gerade nicht abrufen. Das kann heissen, dass Hubra nicht erreichbar ist.',
            'The status cannot be loaded right now. That can mean Hubra is unreachable.',
          )}
        </Alert>
      )}

      {data && (
        <Stack gap="lg">
          <Paper withBorder radius="md" p="md">
            <Group gap="sm" wrap="nowrap" align="flex-start">
              <ThemeIcon size={44} radius="xl" variant="light" color={COLOR[data.overall]}>
                <LevelIcon level={data.overall} size={26} />
              </ThemeIcon>
              <Box>
                <Text fw={700} fz="lg">
                  {headline[data.overall]}
                </Text>
                {data.overall === 'maintenance' && (
                  <Text size="sm" c="dimmed">
                    {data.maintenance.message ||
                      tr('Hubra wird gerade aktualisiert.', 'Hubra is being updated.')}
                    {data.maintenance.until
                      ? tr(` Voraussichtlich bis ${when(data.maintenance.until)}.`, ` Expected until ${when(data.maintenance.until)}.`)
                      : ''}
                  </Text>
                )}
                <Text size="xs" c="dimmed" mt={2}>
                  {tr(`Geprüft ${when(data.checked_at)}`, `Checked ${when(data.checked_at)}`)}
                </Text>
              </Box>
            </Group>
          </Paper>

          {data.maintenance.upcoming && !data.maintenance.active && (
            <Alert color="blue" variant="light" icon={<IconTool size={18} />}>
              {tr(
                `Geplante Wartung ${when(data.maintenance.upcoming.starts_at)} bis ${when(data.maintenance.upcoming.ends_at)}.`,
                `Planned maintenance ${when(data.maintenance.upcoming.starts_at)} to ${when(data.maintenance.upcoming.ends_at)}.`,
              )}{' '}
              {data.maintenance.upcoming.message}
            </Alert>
          )}

          <Paper withBorder radius="md">
            {data.components.map((c, i) => (
              <Group
                key={c.id}
                justify="space-between"
                wrap="nowrap"
                px="md"
                py="sm"
                style={i ? { borderTop: '1px solid var(--mantine-color-default-border)' } : undefined}
              >
                <Text size="sm" fw={600}>
                  {name[c.id]}
                </Text>
                <Group gap={6} wrap="nowrap">
                  <Text size="sm" fw={600} style={{ color: `var(--mantine-color-${COLOR[c.level]}-text)` }}>
                    {levelText[c.level]}
                  </Text>
                  <LevelIcon level={c.level} size={18} />
                </Group>
              </Group>
            ))}
          </Paper>

          <Box>
            <Title order={3} fz="md" mb={8}>
              {tr(`Letzte ${data.history_days} Tage`, `Last ${data.history_days} days`)}
            </Title>
            {data.incidents.length === 0 && data.past_maintenance.length === 0 ? (
              <Text size="sm" c="dimmed">
                {tr('Keine Störungen.', 'No disruptions.')}
              </Text>
            ) : (
              <Stack gap={8}>
                {[
                  ...data.incidents.map((i) => ({
                    at: i.started_at,
                    text: incidentText(i),
                    span: i.ended_at
                      ? tr(`${when(i.started_at)} bis ${when(i.ended_at)}`, `${when(i.started_at)} to ${when(i.ended_at)}`)
                      : tr(`seit ${when(i.started_at)}`, `since ${when(i.started_at)}`),
                    level: (i.ended_at ? 'operational' : i.level) as Level | 'maintenance',
                  })),
                  ...data.past_maintenance.map((w) => ({
                    at: w.starts_at,
                    text: w.message || tr('Wartung', 'Maintenance'),
                    span: tr(`${when(w.starts_at)} bis ${when(w.ends_at)}`, `${when(w.starts_at)} to ${when(w.ends_at)}`),
                    level: 'maintenance' as const,
                  })),
                ]
                  .sort((a, b) => b.at.localeCompare(a.at))
                  .map((row) => (
                    <Group key={`${row.at}-${row.text}`} gap="sm" wrap="nowrap" align="flex-start">
                      <Box pt={2}>
                        <LevelIcon level={row.level} size={16} />
                      </Box>
                      <Box>
                        <Text size="sm">{row.text}</Text>
                        <Text size="xs" c="dimmed">
                          {row.span}
                        </Text>
                      </Box>
                    </Group>
                  ))}
              </Stack>
            )}
          </Box>

          <Anchor size="sm" onClick={() => navigate('/login')}>
            {tr('Zur Anmeldung', 'To sign in')}
          </Anchor>
        </Stack>
      )}
    </AuthFrame>
  )
}
