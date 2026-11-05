import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Anchor,
  Badge,
  Button,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import { DiscordLogPicker } from '@/screens/platform/DiscordLogPicker'
import {
  getPlatformSettings,
  sendPlatformTestDiscord,
  sendPlatformTestMail,
  updatePlatformSettings,
  type PlatformSetting,
} from '@/api/platform'

const RELAY = ['mail.relay.host', 'mail.relay.port', 'mail.relay.user', 'mail.relay.password']
const FALLBACK = [
  'mail.fallback.host',
  'mail.fallback.port',
  'mail.fallback.user',
  'mail.fallback.password',
]
const SENDER = ['mail.system.sender_email', 'mail.system.sender_name']
const BACKUP = [
  'backup.public_key',
  'backup.s3.endpoint',
  'backup.s3.bucket',
  'backup.s3.region',
  'backup.s3.access_key',
  'backup.s3.secret_key',
]

const DISCORD = [
  'discord.client_id',
  'discord.public_key',
  'discord.client_secret',
  'discord.bot_token',
]

const DISCORD_LOG = ['discord.log_channel_id', 'discord.audit_channel_id']
const DISCORD_ROLES = ['discord.platform_roles']
// Defaults built into Hubra, not read from the environment.
const PERF = ['perf.slow_request_ms', 'perf.slow_query_ms', 'perf.p95_warning_ms']
const LIMITS = ['limits.warn_percent']
const MCP = ['mcp.url']
const OAUTH = ['oauth.dynamic_clients', 'oauth.dynamic_redirect_hosts']
const SUPPORT = ['support.url']
const BUILT_IN = ['alerts.cooldown_minutes', 'alerts.retention_days', ...PERF, ...LIMITS, ...OAUTH]
const ALERTS = ['alerts.cooldown_minutes', 'alerts.retention_days', 'alerts.manage_url']


// View Channel + Send Messages + Embed Links
const LOG_BOT_PERMISSIONS = (1 << 10) | (1 << 11) | (1 << 14)
// Manage Roles, only asked for when the bot keeps the platform server's roles.
const MANAGE_ROLES = 1 << 28

/** One group of platform settings; each is shown on the page it configures. */
export type SettingsSectionId =
  | 'relay'
  | 'sender'
  | 'backups'
  | 'discord-app'
  | 'discord-channels'
  | 'alerts'
  | 'performance'
  | 'limits'
  | 'mcp'
  | 'oauth'
  | 'support'
/** The keys each section saves. */
const SECTION_KEYS: Record<SettingsSectionId, string[]> = {
  relay: [...RELAY, ...FALLBACK],
  sender: SENDER,
  backups: BACKUP,
  'discord-app': DISCORD,
  'discord-channels': [...DISCORD_LOG, ...DISCORD_ROLES],
  alerts: ALERTS,
  performance: PERF,
  limits: LIMITS,
  mcp: MCP,
  oauth: OAUTH,
  support: SUPPORT,
}

function SourceBadge({ s }: { s: PlatformSetting }) {
  return s.source === 'platform' ? (
    <Badge size="xs" variant="light">
      {tr('Hier gesetzt', 'Set here')}
    </Badge>
  ) : !s.isSet ? (
    <Badge size="xs" variant="outline" color="gray">
      {tr('Nicht gesetzt', 'Not set')}
    </Badge>
  ) : BUILT_IN.includes(s.key) ? (
    <Badge size="xs" variant="outline" color="gray">
      {tr('Standard', 'Default')}
    </Badge>
  ) : (
    <Badge size="xs" variant="outline" color="gray">
      {tr('Aus der Umgebung', 'From env')}
    </Badge>
  )
}

/**
 * Settings of the whole platform, not of one club: the outbound mail relay
 * (sign-in, SSO and platform mail always go out through it from the system
 * sender; club mail does too, with the club's address as Reply-To) and where
 * the encrypted database backups are stored.
 */
// The backend describes the settings in English; German first here.
const FIELD_DE: Record<string, [string, string]> = {
  'mail.relay.host': [
    'SMTP-Relay-Server',
    'Ausgehender Mailserver für alle Mails, die Hubra verschickt',
  ],
  'mail.relay.port': ['SMTP-Relay-Port', '587 für STARTTLS, 25 für ein internes Relay ohne TLS'],
  'mail.relay.user': ['SMTP-Benutzer', 'Leer lassen, wenn das Relay keine Anmeldung braucht'],
  'mail.relay.password': ['SMTP-Passwort', 'Wird verschlüsselt gespeichert'],
  'mail.fallback.host': [
    'Fallback-Relay-Server',
    'Wird genutzt, wenn das Relay eine Mail ablehnt, z. B. weil das Sendekontingent erreicht ist (smtp-relay.brevo.com). Leer lassen für keinen Fallback',
  ],
  'mail.fallback.port': ['Fallback-Relay-Port', '587 für STARTTLS, 465 für TLS'],
  'mail.fallback.user': [
    'Fallback-SMTP-Benutzer',
    'Leer lassen, wenn der Fallback keine Anmeldung braucht',
  ],
  'mail.fallback.password': ['Fallback-SMTP-Passwort', 'Wird verschlüsselt gespeichert'],
  'mail.system.sender_email': [
    'Absenderadresse des Systems',
    'Absender für Anmelde-, SSO- und Plattform-Mails',
  ],
  'mail.system.sender_name': ['Absendername des Systems', 'Angezeigter Name des Systemabsenders'],
  'backup.public_key': [
    'Öffentlicher Backup-Schlüssel',
    'age-Schlüssel (age1…), mit dem jedes Backup verschlüsselt wird (flask backups keygen). Der private Schlüssel bleibt ausserhalb des Servers; die Wiederherstellung fragt danach',
  ],
  'backup.s3.endpoint': [
    'S3-Endpunkt',
    'S3-kompatible Adresse, z. B. https://eu2.contabostorage.com',
  ],
  'backup.s3.bucket': ['S3-Bucket', 'Bucket, in den die verschlüsselten Backups gehen'],
  'backup.s3.region': ['S3-Region', "Bei Contabo meist 'default'"],
  'backup.s3.access_key': ['S3-Access-Key', 'Wird verschlüsselt gespeichert'],
  'backup.s3.secret_key': ['S3-Secret-Key', 'Wird verschlüsselt gespeichert'],
  'discord.client_id': [
    'Discord-Application-ID',
    'Developer Portal › deine App › General Information › Application ID',
  ],
  'discord.public_key': [
    'Discord-Public-Key',
    'General Information › Public Key; prüft, dass Interaktionen von Discord kommen',
  ],
  'discord.client_secret': [
    'Discord-Client-Secret',
    'OAuth2 › Client Secret. Wird verschlüsselt gespeichert',
  ],
  'discord.bot_token': ['Discord-Bot-Token', 'Bot › Token. Wird verschlüsselt gespeichert'],
  'alerts.cooldown_minutes': [
    'Pause zwischen Warnmails (Minuten)',
    'So lange kommt dieselbe Art Warnung nicht noch einmal per Mail. 0: jedes Mal. Ausfälle und Wiederherstellungen kommen immer',
  ],
  'alerts.retention_days': [
    'Ereignisprotokoll aufbewahren (Tage)',
    'So lange bleiben gesendete und fehlgeschlagene Mails, Ausfälle und Warnungen im Protokoll (1 bis 365)',
  ],
  'mcp.url': [
    'Adresse des Claude-Connectors',
    'Wo der MCP-Server (app/mcp) erreichbar ist; manage zeigt damit den Befehl zum Verbinden (https://mcp.hubra.club). Leer: nicht eingerichtet',
  ],
  'oauth.dynamic_redirect_hosts': [
    'Rücksprung-Adressen für selbst angemeldete Apps',
    'Hosts, zu denen eine selbst angemeldete App zurückführen darf, durch Komma getrennt (Subdomains zählen mit). Leer: jeder https-Host',
  ],
  'support.url': [
    'Adresse der Support-Seite',
    'Hilfe, Roadmap, Status und Meldungen (Image support-frontend), z. B. https://support.hubra.club. Mails an Meldende verlinken dorthin. Leer: auf die Meldungen in der Vereins-App',
  ],
  'alerts.manage_url': [
    'Adresse von manage',
    'Für den Knopf «Warnungen öffnen» in Warnmails, z. B. https://manage.hubra.club. Leer: kein Knopf',
  ],
  'perf.slow_request_ms': [
    'Langsame Anfrage (ms)',
    'API-Anfragen ab dieser Dauer zählen als langsam und kommen ins Log, nur mit der Route. 0: aus',
  ],
  'perf.slow_query_ms': [
    'Langsame Datenbankabfrage (ms)',
    'Abfragen ab dieser Dauer werden gezählt und ins Log geschrieben, ohne ihre Werte. 0: aus',
  ],
  'perf.p95_warning_ms': [
    'Warnung bei langsamer API (ms)',
    'Offenes Problem unter Warnungen, wenn 95 % der Anfragen der letzten Stunde nicht schneller sind. 0: aus',
  ],
  'limits.warn_percent': [
    'Warnen ab (%)',
    'Inhaber und Plattform bekommen eine Meldung, wenn ein Verein diesen Anteil eines Limits erreicht. Die zweite kommt bei 100 %',
  ],
  'discord.log_channel_id': [
    'Kanal für das Plattform-Log',
    'Kanal-ID auf dem Discord-Server der Plattform (Rechtsklick auf den Kanal › Kanal-ID kopieren, Entwicklermodus nötig). Leer: keine Meldungen',
  ],
  'discord.audit_channel_id': [
    'Audit-Kanal',
    'Kanal-ID für jeden Eintrag im Audit-Log, mit Links in manage. Warnungen bleiben im Plattform-Log. Leer: aus',
  ],
}

/**
 * One group of platform settings (not of one club), shown on the page it
 * belongs to: the mail relay under Mail, the backup storage under Backups,
 * plan limits under All clubs, and so on. Each section saves on its own.
 */
export function SettingsSection({ section }: { section: SettingsSectionId }) {
  const { notify } = useAdmin()
  const { tr } = useLang()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { data: settings = [], isLoading } = useQuery({
    queryKey: ['platform-settings'],
    queryFn: getPlatformSettings,
  })
  // Only the fields edited since the last save; the rest show the saved value.
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState<'relay' | 'fallback' | null>(null)
  const [testingDiscord, setTestingDiscord] = useState<'log' | 'audit' | null>(null)

  const byKey = Object.fromEntries(settings.map((s) => [s.key, s]))
  // A secret field left empty keeps the stored value. Only this section's
  // fields count, so a half-edited field elsewhere is never saved here.
  const changed = settings.filter(
    (s) =>
      SECTION_KEYS[section].includes(s.key) &&
      (s.secret ? !!draft[s.key] : s.key in draft && draft[s.key] !== s.value),
  )

  const save = async (values: Record<string, string | null>) => {
    setSaving(true)
    try {
      const fresh = await updatePlatformSettings(values)
      queryClient.setQueryData(['platform-settings'], fresh)
      setDraft({})
      notify('success', tr('Plattform-Einstellungen gespeichert', 'Platform settings saved'))
    } catch (err) {
      // Name the fields the server refused, not only "Invalid platform settings".
      const details = (err as { details?: Record<string, unknown> }).details
      const fields = details
        ? Object.entries(details)
            .map(([k, v]) => `${byKey[k]?.label ?? k}: ${String(v)}`)
            .join(' · ')
        : ''
      notify(
        'error',
        tr('Speichern fehlgeschlagen', 'Could not save'),
        fields || (err instanceof Error ? err.message : undefined),
      )
    } finally {
      setSaving(false)
    }
  }

  const sendTest = async (via: 'relay' | 'fallback') => {
    setTesting(via)
    try {
      await sendPlatformTestMail(testTo.trim(), via)
      notify('success', tr('Testmail gesendet', 'Test mail sent'), testTo.trim())
    } catch (err) {
      notify(
        'error',
        tr('Testmail fehlgeschlagen', 'Test mail failed'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setTesting(null)
    }
  }

  const sendDiscordTest = async (channel: 'log' | 'audit' = 'log') => {
    setTestingDiscord(channel)
    try {
      await sendPlatformTestDiscord(channel)
      notify('success', tr('Testnachricht gesendet', 'Test message sent'))
    } catch (err) {
      notify(
        'error',
        tr('Testnachricht fehlgeschlagen', 'Test message failed'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setTestingDiscord(null)
    }
  }

  const clientId = byKey['discord.client_id']?.value ?? ''
  const logChanged = changed.some((s) => DISCORD_LOG.includes(s.key))
  const logChannel =
    draft['discord.log_channel_id'] ?? byKey['discord.log_channel_id']?.value ?? ''
  const auditChannel =
    draft['discord.audit_channel_id'] ?? byKey['discord.audit_channel_id']?.value ?? ''
  const manageUrl = byKey['alerts.manage_url']?.value ?? ''

  const rolesOn =
    (draft['discord.platform_roles'] ?? byKey['discord.platform_roles']?.value) === 'on'
  const botAddLink = clientId ? (
    <Anchor
      href={`https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(clientId)}&scope=bot&permissions=${LOG_BOT_PERMISSIONS | (rolesOn ? MANAGE_ROLES : 0)}`}
      target="_blank"
      rel="noreferrer"
    >
      {tr('Bot zum Plattform-Server hinzufügen', 'Add the bot to the platform server')}
    </Anchor>
  ) : (
    <Text span size="sm" c="dimmed">
      {tr(
        'Zuerst die Discord-Anwendungs-ID unter Einrichtung eintragen.',
        'Set the Discord application ID under Setup first.',
      )}
    </Text>
  )

  const field = (key: string) => {
    const s = byKey[key]
    if (!s) return null
    const de = FIELD_DE[key]
    const label = (
      <Group gap={6} component="span">
        {de ? tr(de[0], s.label) : s.label}
        <SourceBadge s={s} />
      </Group>
    )
    const common = {
      label,
      description: de ? tr(de[1], s.description) : s.description,
      value: draft[key] ?? s.value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        // Read it now: the updater runs after React has cleared currentTarget.
        const value = e.currentTarget.value
        setDraft((d) => ({ ...d, [key]: value }))
      },
    }
    return s.secret ? (
      <PasswordInput
        key={key}
        {...common}
        placeholder={s.isSet ? tr('•••••••• (unverändert)', '•••••••• (unchanged)') : ''}
      />
    ) : (
      <TextInput key={key} {...common} />
    )
  }

  const resetButton = (keys: string[]) =>
    keys.some((k) => byKey[k]?.source === 'platform') && (
      <Button
        variant="subtle"
        color="gray"
        size="xs"
        disabled={saving}
        onClick={() =>
          save(
            Object.fromEntries(
              keys.filter((k) => byKey[k]?.source === 'platform').map((k) => [k, null]),
            ),
          )
        }
      >
        {tr('Auf Umgebung zurücksetzen', 'Reset to env')}
      </Button>
    )

  return (
    <div>
      {isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : (
        <Stack gap={20} maw={720}>
          {section === 'relay' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Mail-Relay', 'Relay')}</Title>
                {resetButton(RELAY)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Jede Mail von Hubra geht über dieses Relay. Anmeldung, SSO und Plattform-Hinweise kommen vom Systemabsender. Vereinsmails ebenfalls, mit der Vereinsadresse als Antwortadresse, ausser der Verein hat ein eigenes Absender-Postfach.',
                  "Every mail Hubra sends goes through this relay. Sign-in, SSO and platform notices come from the system sender. Club mail does too, with the club's address as Reply-To, unless the club has its own sender mailbox.",
                )}
              </Text>
              <Stack gap="sm">{RELAY.map(field)}</Stack>
            </Paper>
          )}

          {section === 'relay' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Fallback-Relay', 'Fallback relay')}</Title>
                {resetButton(FALLBACK)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Lehnt das Relay eine Mail ab (Kontingent erreicht, Ausfall, Anmeldung), geht sie über diesen Server raus, vom selben Absender. Danach wird das Relay 15 Minuten übersprungen. Die Absenderdomain muss auch beim Fallback-Anbieter verifiziert sein (SPF/DKIM).',
                  'When the relay refuses a mail (quota reached, outage, login), it goes out through this server, from the same sender. The relay is then skipped for 15 minutes. The sender domain must be verified with the fallback provider too (SPF/DKIM).',
                )}
              </Text>
              <Stack gap="sm">{FALLBACK.map(field)}</Stack>
            </Paper>
          )}

          {section === 'sender' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={12}>
                <Title order={3}>{tr('Systemabsender', 'System sender')}</Title>
                {resetButton(SENDER)}
              </Group>
              <Stack gap="sm">{SENDER.map(field)}</Stack>
            </Paper>
          )}

          {section === 'alerts' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Versand der Warnungen', 'Alert delivery')}</Title>
                {resetButton(ALERTS)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Warnmails gehen an Plattform-Admins (Superadmins und Rollen mit Plattform-Einstellungen), nicht an Support. Jede Person wählt unter Warnungen › Meine Warnungen, welche sie bekommt.',
                  'Alert mails go to platform admins (superadmins and roles with platform settings), not to Support. Each person picks which ones they get under Alerts › My alerts.',
                )}
              </Text>
              <Stack gap="sm">{ALERTS.map(field)}</Stack>
            </Paper>
          )}

          {section === 'performance' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Grenzwerte', 'Thresholds')}</Title>
                {resetButton(PERF)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Grenzwerte für diese Seite und die Warnung bei langsamer API. Gemessen werden nur Routenmuster und die Form der Abfragen, keine Pfade, Werte oder Personen.',
                  'Thresholds for this page and the slow-API alert. Only route patterns and query shapes are measured, no paths, values or people.',
                )}
              </Text>
              <Stack gap="sm">{PERF.map(field)}</Stack>
            </Paper>
          )}

          {section === 'mcp' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Adresse des Connectors', 'Connector address')}</Title>
                {resetButton(MCP)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Wo der MCP-Server (Image mcp) läuft. Er hat keinen Datenbankzugriff und keine eigenen Zugangsdaten: jede Anfrage nutzt das Token der Person.',
                  'Where the MCP server (the mcp image) runs. It has no database access and no credentials of its own: every request uses the person\'s token.',
                )}
              </Text>
              <Stack gap="sm">{MCP.map(field)}</Stack>
            </Paper>
          )}

          {section === 'oauth' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Selbst angemeldete Apps', 'Self-registered apps')}</Title>
                {resetButton(OAUTH)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Claude meldet sich beim ersten Verbinden selbst als App an (OAuth Dynamic Client Registration). Solche Apps dürfen nur über den Claude-Connector lesen, und die Person sieht beim Erlauben, dass Hubra sie nicht geprüft hat und wohin sie zurückführt.',
                  'Claude registers itself as an app when it first connects (OAuth dynamic client registration). Such apps may only read through the Claude connector, and the person sees when allowing that Hubra has not checked them and where they lead back to.',
                )}
              </Text>
              <Stack gap="sm">
                {byKey['oauth.dynamic_clients'] && (
                  <Switch
                    label={tr('Selbst anmelden erlauben', 'Allow self-registration')}
                    checked={(draft['oauth.dynamic_clients'] ?? byKey['oauth.dynamic_clients'].value) === 'on'}
                    onChange={(e) => {
                      const on = e.currentTarget.checked
                      setDraft((d) => ({ ...d, 'oauth.dynamic_clients': on ? 'on' : 'off' }))
                    }}
                  />
                )}
                {field('oauth.dynamic_redirect_hosts')}
              </Stack>
            </Paper>
          )}

          {section === 'support' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Support-Seite', 'Support site')}</Title>
                {resetButton(SUPPORT)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Wo die Support-Seite läuft. Antworten auf Meldungen und die Mail nach einer Passwortänderung verlinken dorthin.',
                  'Where the support site runs. Answers to reports and the password-changed mail link there.',
                )}
              </Text>
              <Stack gap="sm">{SUPPORT.map(field)}</Stack>
            </Paper>
          )}

          {section === 'limits' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Limit-Warnungen', 'Limit warnings')}</Title>
                {resetButton(LIMITS)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Die Limits stehen bei jedem Tarif (oben). Ist das Mitgliederlimit erreicht, kommt niemand Neues dazu (Einladungen, Anträge); Plattform-Staff kann in manage trotzdem hinzufügen. Mails pro Monat und Speicher werden nur gemeldet, nichts wird gesperrt. Einzelne Vereine bekommen eigene Limits auf ihrer Seite.',
                  'The limits are on each plan (above). At the member limit nobody new can join (invites, applications); platform staff can still add people in manage. Mails per month and storage are only reported, nothing is blocked. A club gets its own limits on its page.',
                )}
              </Text>
              <Stack gap="md">{field('limits.warn_percent')}</Stack>
            </Paper>
          )}

          {section === 'backups' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Backup-Speicher', 'Backup storage')}</Title>
                {resetButton(BACKUP)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Hierhin gehen das globale Backup und die Backups jedes Vereins, verschlüsselt mit dem öffentlichen Backup-Schlüssel. Er ist nicht geheim; den privaten Schlüssel braucht es nur zum Öffnen, und er gehört nicht auf den Server.',
                  'The global backup and every club backup go here, encrypted to the backup public key. It is not secret; the private key is only needed to open a backup and does not belong on the server.',
                )}
              </Text>
              <Stack gap="sm">{BACKUP.map(field)}</Stack>
            </Paper>
          )}

          {section === 'discord-app' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Discord-App', 'Discord app')}</Title>
                {resetButton(DISCORD)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Die eine Hubra-App auf Discord: Vereine fügen damit den Bot zu ihrem Server hinzu, Mitglieder verknüpfen ihr Konto. Einrichtung in docs/discord.md. Ohne diese Werte ist Discord für Vereine nicht verfügbar.',
                  'The one Hubra application on Discord: clubs add the bot to their server with it, members link their account. Setup in docs/discord.md. Without these values Discord is not available to clubs.',
                )}
              </Text>
              <Stack gap="sm">{DISCORD.map(field)}</Stack>
            </Paper>
          )}

          {section === 'discord-channels' && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Plattform-Log', 'Platform log')}</Title>
                {resetButton(DISCORD_LOG)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Der Hubra-Bot meldet Plattform-Ereignisse auf dem Discord-Server der Plattform: neue Vereine und Anfragen, Rollen, Plugins, Backups, Einstellungen und Systemwarnungen. Mit einem Audit-Kanal gehen die Audit-Einträge dorthin und das Plattform-Log behält die Warnungen; jede Meldung kommt nur einmal. Braucht den Bot-Token unter Einrichtung.',
                  "The Hubra bot posts platform events on the platform's own Discord server: new clubs and requests, roles, plugins, backups, settings and system alerts. With an audit channel, audit entries go there and the platform log keeps the alerts; each post goes out once. Needs the bot token under Setup.",
                )}
              </Text>
              <Stack gap="sm">
                <DiscordLogPicker
                  botTokenSet={!!byKey['discord.bot_token']?.isSet}
                  addLink={botAddLink}
                  slots={[
                    {
                      label: tr('Kanal für das Plattform-Log', 'Channel for the platform log'),
                      description: tr(
                        'Systemwarnungen, und die Plattform-Ereignisse, solange es keinen Audit-Kanal gibt.',
                        'System alerts, and the platform events while there is no audit channel.',
                      ),
                      channelId: logChannel,
                      onChange: (id) => setDraft((d) => ({ ...d, 'discord.log_channel_id': id })),
                      fallback: field('discord.log_channel_id'),
                      suggestedName: 'hubra-log',
                    },
                    {
                      label: tr('Audit-Kanal (optional)', 'Audit channel (optional)'),
                      description: tr(
                        'Gewählt: Die Einträge aus dem Audit-Log gehen nur hierhin, mit Links in manage. Leer: aus.',
                        'Picked: audit log entries go here only, with links into manage. Empty: off.',
                      ),
                      channelId: auditChannel,
                      onChange: (id) => setDraft((d) => ({ ...d, 'discord.audit_channel_id': id })),
                      fallback: field('discord.audit_channel_id'),
                      suggestedName: 'hubra-audit',
                    },
                  ]}
                />
                <Text size="sm">
                  {tr('Was wohin gemeldet wird, steht in der ', 'What is posted where is set in the ')}
                  <Anchor
                    component="button"
                    type="button"
                    size="sm"
                    onClick={() => navigate('/app/platform/alerts/rules')}
                  >
                    {tr('Benachrichtigungs-Matrix unter Warnungen', 'notification matrix under Alerts')}
                  </Anchor>
                  .
                </Text>
                {!manageUrl && (
                  <Text size="xs" c="orange">
                    {tr(
                      'Ohne Manage-Adresse kommen die Meldungen ohne Links. ',
                      'Without the manage address, posts come without links. ',
                    )}
                    <Anchor
                      component="button"
                      type="button"
                      size="xs"
                      onClick={() => navigate('/app/platform/alerts/rules')}
                    >
                      {tr('Unter Warnungen eintragen', 'Set it under Alerts')}
                    </Anchor>
                  </Text>
                )}
                <Group>
                  <Button
                    variant="light"
                    loading={testingDiscord === 'log'}
                    disabled={logChanged || !byKey['discord.log_channel_id']?.value}
                    onClick={() => sendDiscordTest('log')}
                  >
                    {tr('Test ins Plattform-Log', 'Test the platform log')}
                  </Button>
                  {byKey['discord.audit_channel_id']?.value && (
                    <Button
                      variant="light"
                      loading={testingDiscord === 'audit'}
                      disabled={logChanged}
                      onClick={() => sendDiscordTest('audit')}
                    >
                      {tr('Test in den Audit-Kanal', 'Test the audit channel')}
                    </Button>
                  )}
                  {logChanged && (
                    <Text size="xs" c="dimmed">
                      {tr('Zuerst speichern.', 'Save first.')}
                    </Text>
                  )}
                </Group>
              </Stack>
            </Paper>
          )}

          {section === 'discord-channels' && byKey['discord.platform_roles'] && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>
                  {tr('Rollen auf dem Plattform-Server', 'Roles on the platform server')}
                </Title>
                {resetButton(DISCORD_ROLES)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Wer sein Discord-Konto verknüpft hat, bekommt auf dem Server des Plattform-Logs automatisch die passenden Rollen: Plattform-Admin (mit Zwei-Faktor), Vereinsinhaber, Vereinsadmin und Vereinsmitglied. Der Bot macht die Rollen selbst, ohne Rechte; was sie sehen dürfen, stellst du in Discord ein. Andere Rollen fasst er nie an. Ausschalten löscht diese Rollen wieder.',
                  'Everyone who linked their Discord account gets the matching roles on the platform log’s server: Plattform-Admin (with two-factor), Vereinsinhaber (club owner), Vereinsadmin (club admin) and Vereinsmitglied (club member). The bot makes these roles itself, without permissions; what they may see is set in Discord. It never touches other roles. Turning this off deletes the roles again.',
                )}
              </Text>
              <Switch
                label={tr('Rollen automatisch vergeben', 'Give roles automatically')}
                checked={rolesOn}
                onChange={(e) => {
                  const on = e.currentTarget.checked
                  setDraft((d) => ({ ...d, 'discord.platform_roles': on ? 'on' : 'off' }))
                }}
              />
              <Text size="xs" c="dimmed" mt={8}>
                {tr(
                  'Braucht das Recht «Rollen verwalten» für den Bot auf diesem Server. Änderungen kommen innert zehn Minuten an.',
                  'The bot needs the “Manage Roles” permission on this server. Changes arrive within ten minutes.',
                )}
              </Text>
            </Paper>
          )}

          <Group>
            <Button
              loading={saving}
              disabled={changed.length === 0}
              onClick={() => save(Object.fromEntries(changed.map((s) => [s.key, draft[s.key]])))}
            >
              {tr('Speichern', 'Save')}
            </Button>
          </Group>

          {section === 'relay' && (
            <Paper withBorder p="lg">
              <Title order={3} mb={12}>
                {tr('Testmail', 'Test mail')}
              </Title>
              <Group align="flex-end">
                <TextInput
                  label={tr('Senden an', 'Send to')}
                  placeholder={tr('du@beispiel.ch', 'you@example.com')}
                  value={testTo}
                  onChange={(e) => setTestTo(e.currentTarget.value)}
                  style={{ flex: 1, minWidth: 220 }}
                />
                <Button
                  variant="light"
                  loading={testing === 'relay'}
                  disabled={!testTo.includes('@') || changed.length > 0 || testing !== null}
                  onClick={() => sendTest('relay')}
                >
                  {tr('Test über Relay', 'Test via relay')}
                </Button>
                {byKey['mail.fallback.host']?.isSet && (
                  <Button
                    variant="light"
                    loading={testing === 'fallback'}
                    disabled={!testTo.includes('@') || changed.length > 0 || testing !== null}
                    onClick={() => sendTest('fallback')}
                  >
                    {tr('Test über Fallback', 'Test via fallback')}
                  </Button>
                )}
              </Group>
              {changed.length > 0 && (
                <Text size="xs" c="dimmed" mt={6}>
                  {tr(
                    'Speichere zuerst deine Änderungen; der Test nutzt die gespeicherten Einstellungen.',
                    'Save your changes first; the test uses the saved settings.',
                  )}
                </Text>
              )}
            </Paper>
          )}
        </Stack>
      )}
    </div>
  )
}
