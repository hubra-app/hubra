import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Anchor, Badge, Button, Code, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import { checkDiscordNow, getDiscordStatus, type DiscordStatus } from '@/api/platform'
import { Row } from './StatusRow'

const MONO = "'JetBrains Mono', monospace"

const CATEGORY_LABEL: Record<string, [string, string]> = {
  clubs: ['Vereine', 'Clubs'],
  requests: ['Anfragen', 'Requests'],
  access: ['Zugriff', 'Access'],
  members: ['Mitglieder', 'Members'],
  plugins: ['Plugins', 'Plugins'],
  backups: ['Backups', 'Backups'],
  platform: ['Plattform', 'Platform'],
  alerts: ['Warnungen', 'Alerts'],
}

const when = (iso?: string | null) => (iso ? formatDateTime(iso) : '—')

function ErrorText({ children }: { children: React.ReactNode }) {
  return (
    <Text size="xs" c="red.8" style={{ wordBreak: 'break-word' }}>
      {children}
    </Text>
  )
}

function BotCard({
  s,
  onCheck,
  checking,
}: {
  s: DiscordStatus
  onCheck: () => void
  checking: boolean
}) {
  const navigate = useNavigate()
  const { settings, check, interactions, plugin } = s
  const missing = [
    !settings.clientId && tr('Anwendungs-ID', 'application ID'),
    !settings.publicKey && tr('Public Key', 'public key'),
    !settings.clientSecret && tr('Client Secret', 'client secret'),
    !settings.botToken && tr('Bot-Token', 'bot token'),
  ].filter(Boolean) as string[]
  const urlMatches =
    interactions.actual == null || !interactions.expected
      ? null
      : interactions.actual === interactions.expected

  return (
    <Paper withBorder p="lg">
      <Group justify="space-between" mb={8} wrap="wrap">
        <Title order={3}>{tr('Discord-Bot', 'Discord bot')}</Title>
        <Group gap={8}>
          {check.checkedAt && (
            <Text size="xs" c="dimmed">
              {tr('Geprüft', 'Checked')} {when(check.checkedAt)}
            </Text>
          )}
          <Button
            variant="subtle"
            size="sm"
            leftSection={<IconRefresh size={14} />}
            onClick={onCheck}
            loading={checking}
            disabled={!settings.botToken}
          >
            {tr('Jetzt prüfen', 'Check now')}
          </Button>
        </Group>
      </Group>

      <Row
        ok={missing.length === 0 ? true : settings.clientId && settings.botToken ? null : false}
        label={tr('Einstellungen', 'Settings')}
      >
        {missing.length === 0 ? (
          <Text size="sm">{tr('Alle gesetzt', 'All set')}</Text>
        ) : (
          <Text size="sm">
            {tr('Fehlt: ', 'Missing: ')}
            {missing.join(', ')}{' '}
            <Anchor size="sm" onClick={() => navigate('/app/platform/discord/settings')}>
              {tr('Einstellungen öffnen', 'Open settings')}
            </Anchor>
          </Text>
        )}
      </Row>

      <Row ok={check.botOk} label={tr('Bot-Anmeldung', 'Bot sign-in')}>
        {check.botOk ? (
          <Text size="sm">
            {tr('Angemeldet als', 'Signed in as')} <b>{check.botUser?.username}</b>{' '}
            <Text span size="xs" c="dimmed" ff={MONO}>
              {check.botUser?.id}
            </Text>
          </Text>
        ) : check.botOk === false ? (
          <ErrorText>{check.botError}</ErrorText>
        ) : (
          <Text size="sm" c="dimmed">
            {tr('Kein Bot-Token gesetzt', 'No bot token set')}
          </Text>
        )}
        {check.appIdMismatch && (
          <ErrorText>
            {tr(
              `Der Token gehört zur Anwendung ${check.appIdMismatch}, nicht zur eingetragenen Anwendungs-ID.`,
              `The token belongs to application ${check.appIdMismatch}, not the application ID set here.`,
            )}
          </ErrorText>
        )}
      </Row>

      {check.botOk && (
        <Row ok={check.guildError ? false : true} label={tr('Server', 'Servers')}>
          {check.guildError ? (
            <ErrorText>{check.guildError}</ErrorText>
          ) : (
            <Text size="sm">
              {tr(`Auf ${check.guildCount ?? 0} Servern`, `On ${check.guildCount ?? 0} servers`)}
            </Text>
          )}
        </Row>
      )}

      {check.botOk && (
        <Row
          ok={check.interactionsError ? false : urlMatches}
          label={tr('Interactions-URL', 'Interactions URL')}
        >
          {check.interactionsError ? (
            <ErrorText>{check.interactionsError}</ErrorText>
          ) : (
            <Stack gap={2}>
              <Text size="xs" ff={MONO} style={{ wordBreak: 'break-all' }}>
                {interactions.actual || tr('nicht gesetzt', 'not set')}
              </Text>
              {urlMatches === false && (
                <Text size="xs" c="orange.8" style={{ wordBreak: 'break-all' }}>
                  {tr('Erwartet: ', 'Expected: ')}
                  {interactions.expected}
                </Text>
              )}
              {!interactions.expected && (
                <Text size="xs" c="dimmed">
                  {tr(
                    'API_PUBLIC_URL ist nicht gesetzt; die erwartete URL ist unbekannt.',
                    'API_PUBLIC_URL is not set, so the expected URL is unknown.',
                  )}
                </Text>
              )}
            </Stack>
          )}
        </Row>
      )}

      <Row
        ok={plugin.installed ? !plugin.error : null}
        label={tr('Discord-Plugin', 'Discord plugin')}
      >
        <Text size="sm">
          {plugin.installed
            ? `${tr('Installiert', 'Installed')} · v${plugin.version}`
            : tr(
                'Nicht installiert: Vereine können Discord nicht verbinden',
                'Not installed: clubs cannot connect Discord',
              )}
        </Text>
        {plugin.error && <ErrorText>{plugin.error}</ErrorText>}
      </Row>

      <Row ok={null} label={tr('Verknüpfte Konten', 'Linked accounts')}>
        <Text size="sm">{s.linkedAccounts}</Text>
      </Row>
    </Paper>
  )
}

function PlatformLogCard({ s }: { s: DiscordStatus }) {
  const navigate = useNavigate()
  const log = s.platformLog
  const failing = !!log.lastErrorAt && log.lastErrorAt > (log.lastOkAt ?? '')
  return (
    <Paper withBorder p="lg">
      <Group justify="space-between" mb={8} wrap="wrap">
        <Title order={3}>{tr('Plattform-Log', 'Platform log')}</Title>
        <Anchor size="sm" onClick={() => navigate('/app/platform/discord/settings')}>
          {tr('Einstellungen', 'Settings')}
        </Anchor>
      </Group>
      <Row ok={!log.channelId ? null : (s.check.channelOk ?? null)} label={tr('Kanal', 'Channel')}>
        {!log.channelId ? (
          <Text size="sm" c="dimmed">
            {tr('Kein Kanal gesetzt: es wird nichts gemeldet', 'No channel set: nothing is posted')}
          </Text>
        ) : (
          <>
            <Text size="sm">
              {s.check.channelName ? `#${s.check.channelName} ` : ''}
              <Text span size="xs" c="dimmed" ff={MONO}>
                {log.channelId}
              </Text>
            </Text>
            {s.check.channelError && <ErrorText>{s.check.channelError}</ErrorText>}
          </>
        )}
      </Row>
      <Row ok={null} label={tr('Was gemeldet wird', 'What is posted')}>
        <Group gap={4}>
          {log.categories.length === 0 ? (
            <Text size="sm" c="dimmed">
              {tr('Nichts', 'Nothing')}
            </Text>
          ) : (
            log.categories.map((c) => (
              <Badge key={c} size="sm" variant="light">
                {CATEGORY_LABEL[c] ? tr(...CATEGORY_LABEL[c]) : c}
              </Badge>
            ))
          )}
        </Group>
      </Row>
      <Row
        ok={log.lastOkAt ? !failing : failing ? false : null}
        label={tr('Letzte Meldung', 'Last post')}
      >
        <Text size="sm">{when(log.lastOkAt)}</Text>
        {failing && (
          <ErrorText>
            {when(log.lastErrorAt)}: {log.lastError}
          </ErrorText>
        )}
      </Row>
    </Paper>
  )
}

function ServersCard({ s }: { s: DiscordStatus }) {
  const navigate = useNavigate()
  const failing = s.servers.filter((srv) => srv.lastError || srv.botOnServer === false).length
  return (
    <Paper withBorder p="lg">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <div>
          <Title order={3} mb={4}>
            {tr('Vereinsserver', 'Club servers')}
          </Title>
          <Text size="sm">
            {s.servers.length === 0
              ? tr('Noch kein Verein hat Discord verbunden.', 'No club has connected Discord yet.')
              : tr(
                  `${s.servers.length} Server verbunden, ${failing} mit Fehlern.`,
                  `${s.servers.length} servers connected, ${failing} with errors.`,
                )}
          </Text>
        </div>
        <Button variant="default" size="sm" onClick={() => navigate('/app/platform/discord/clubs')}>
          {tr('Zur Übersicht', 'Open overview')}
        </Button>
      </Group>
    </Paper>
  )
}

function SetupCard({ s }: { s: DiscordStatus }) {
  const value = (v: string) => (
    <Code block style={{ wordBreak: 'break-all', whiteSpace: 'pre-wrap' }}>
      {v}
    </Code>
  )
  return (
    <Paper withBorder p="lg">
      <Title order={3} mb={4}>
        {tr('Werte für das Developer Portal', 'Values for the Developer Portal')}
      </Title>
      <Text size="xs" c="dimmed" mb={12}>
        {tr(
          'Diese Adressen in der Discord-Anwendung eintragen. Die ganze Anleitung steht in docs/discord.md.',
          'Enter these in the Discord application. The full guide is in docs/discord.md.',
        )}
      </Text>
      <Stack gap="sm">
        <div>
          <Text size="sm" fw={600}>
            {tr('OAuth2 › Redirects (beide)', 'OAuth2 › Redirects (both)')}
          </Text>
          {s.redirectUris.map((u) => (
            <div key={u}>{value(u)}</div>
          ))}
        </div>
        <div>
          <Text size="sm" fw={600}>
            {tr(
              'General Information › Interactions Endpoint URL',
              'General Information › Interactions Endpoint URL',
            )}
          </Text>
          {value(s.interactions.expected)}
        </div>
        {s.linkedRolesUrl && (
          <div>
            <Text size="sm" fw={600}>
              {tr(
                'General Information › Linked Roles Verification URL',
                'General Information › Linked Roles Verification URL',
              )}
            </Text>
            {value(s.linkedRolesUrl)}
          </div>
        )}
        <div>
          <Text size="sm" fw={600}>
            {tr('Bot › Privileged Gateway Intents', 'Bot › Privileged Gateway Intents')}
          </Text>
          <Text size="sm">
            {tr(
              'Server Members Intent an (für den Willkommensgruss), Presence und Message Content aus. Public Bot an, Requires OAuth2 Code Grant aus.',
              'Server Members Intent on (for the welcome message), Presence and Message Content off. Public Bot on, Requires OAuth2 Code Grant off.',
            )}
          </Text>
        </div>
        <div>
          <Text size="sm" fw={600}>
            {tr('Berechtigungen', 'Permissions')}
          </Text>
          <Text size="sm">
            {tr(
              'Hubra fragt sie beim Hinzufügen selbst an, nie Administrator: Nickname ändern, Kanäle ansehen, Nachrichten senden, Links einbetten, dazu Rollen verwalten, Kanäle verwalten (mit Nachrichtenverlauf lesen) und Events erstellen nur wenn der Verein das freigibt.',
              'Hubra asks for them itself when the bot is added, never Administrator: Change Nickname, View Channels, Send Messages, Embed Links, plus Manage Roles, Manage Channels (with Read Message History) and Create Events only when a club allows them.',
            )}
          </Text>
        </div>
      </Stack>
    </Paper>
  )
}

export function DiscordPanel() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['discord-status'], queryFn: getDiscordStatus })
  const [checking, setChecking] = useState(false)

  const checkNow = async () => {
    setChecking(true)
    try {
      queryClient.setQueryData(['discord-status'], await checkDiscordNow())
    } catch (err) {
      notify(
        'error',
        tr('Prüfung fehlgeschlagen', 'Check failed'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setChecking(false)
    }
  }

  if (query.isLoading) return <Text c="dimmed">{tr('Wird geprüft …', 'Checking…')}</Text>
  if (query.isError || !query.data)
    return (
      <Text c="red">
        {query.error instanceof Error
          ? query.error.message
          : tr('Unbekannter Fehler', 'Unknown error')}
      </Text>
    )
  const s = query.data
  return (
    <Stack gap={16}>
      {!s.configured && (
        <Paper withBorder p="md">
          <Text size="sm">
            {tr(
              'Discord ist auf dieser Plattform nicht eingerichtet. Die Schritte stehen in ',
              'Discord is not set up on this platform. The steps are in ',
            )}
            <Code>docs/discord.md</Code>.
          </Text>
        </Paper>
      )}
      <BotCard s={s} onCheck={checkNow} checking={checking} />
      <PlatformLogCard s={s} />
      <ServersCard s={s} />
      <SetupCard s={s} />
    </Stack>
  )
}
