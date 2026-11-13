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
  SegmentedControl,
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
import { SETTINGS_GROUPS } from '@/screens/platform/settings/registry'

const RELAY = ['mail.relay.host', 'mail.relay.port', 'mail.relay.user', 'mail.relay.password']
const FALLBACK = [
  'mail.fallback.host',
  'mail.fallback.port',
  'mail.fallback.user',
  'mail.fallback.password',
]
const SENDER = ['mail.system.sender_email', 'mail.system.sender_name']

// stripe.mode sits under Online payments, on the same page; it applies to both.

const DISCORD_LOG = [
  'discord.log_channel_id',
  'discord.audit_channel_id',
  'discord.changelog_channel_id',
  'discord.language',
]
const DISCORD_ROLES = ['discord.platform_roles']
const DISCORD_SUPPORT = ['discord.support_channel_id', 'discord.support_add_reporters']
// Defaults built into Hubra, not read from the environment.
const PERF = ['perf.slow_request_ms', 'perf.slow_query_ms', 'perf.p95_warning_ms']
const ERRORS = ['errors.auto_resolve']
const UPGRADES = ['upgrades.post_deploy_steps']
const LIMITS = ['limits.warn_percent', 'limits.grace_days']
const OAUTH = ['oauth.dynamic_clients', 'oauth.dynamic_redirect_hosts']
const BUILT_IN = [
  ...PERF, ...ERRORS, ...UPGRADES, ...LIMITS, ...OAUTH,
  ...Object.values(SETTINGS_GROUPS).flatMap((g) => g.builtIn ?? []),
]


// View Channel + Send Messages + Embed Links
const LOG_BOT_PERMISSIONS = (1 << 10) | (1 << 11) | (1 << 14)
// Manage Roles, only asked for when the bot keeps the platform server's roles.
const MANAGE_ROLES = 1 << 28
// Support threads: create invite, read message history, manage threads,
// create private threads, send messages in threads. Above 2^31, so added up
// as numbers (JavaScript's | works on 32 bits).
const THREAD_PERMISSIONS = 2 ** 0 + 2 ** 16 + 2 ** 34 + 2 ** 36 + 2 ** 38

/** One group of platform settings; each is shown on the page it configures. */
type OwnSectionId =
  | 'relay'
  | 'sender'
  | 'discord-channels'
  | 'performance'
  | 'limits'
  | 'oauth'
/**
 * One group of platform settings, shown on the page it configures: one of
 * the groups below, or a plain one from settings/ (see settings/registry.ts).
 */
export type SettingsSectionId = OwnSectionId | (string & {})

/** The keys each section below saves. */
const SECTION_KEYS: Record<OwnSectionId, string[]> = {
  relay: [...RELAY, ...FALLBACK],
  sender: SENDER,
  'discord-channels': [...DISCORD_LOG, ...DISCORD_ROLES, ...DISCORD_SUPPORT],
  performance: [...PERF, ...ERRORS],
  limits: LIMITS,
  oauth: OAUTH,
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
  'oauth.dynamic_redirect_hosts': [
    'Rücksprung-Adressen für selbst angemeldete Apps',
    'Hosts, zu denen eine selbst angemeldete App zurückführen darf, durch Komma getrennt (Subdomains zählen mit). Leer: jeder https-Host',
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
  'errors.auto_resolve': [
    'Fehler beim Upgrade als behoben markieren',
    'Wenn alle Prozesse eine neue Version laufen, gelten offene Fehler, die dort nicht aufgetreten sind, als behoben. Kommen sie wieder, sind sie wieder offen',
  ],
  'upgrades.post_deploy_steps': [
    'Schritte nach dem Deploy',
    'Läuft auf allen Prozessen eine neue Version, führt ein Worker Migrationen, Seeds, Rechte-Abgleich und Plugin-Sync aus und meldet unter Systemzustand',
  ],
  'limits.warn_percent': [
    'Warnen ab (%)',
    'Inhaber und Plattform bekommen eine Meldung, wenn ein Verein diesen Anteil eines Limits erreicht. Die zweite kommt bei 100 %',
  ],
  'limits.grace_days': [
    'Kulanzfrist am Mitgliederlimit (Tage)',
    'So lange nimmt ein Verein am Mitgliederlimit noch neue Mitglieder auf, ab dem ersten Beitritt darüber. Die Admins sehen dabei, welcher Tarif passt. 0: kein neues Mitglied über dem Limit',
  ],
  'discord.log_channel_id': [
    'Kanal für das Plattform-Log',
    'Kanal-ID auf dem Discord-Server der Plattform (Rechtsklick auf den Kanal › Kanal-ID kopieren, Entwicklermodus nötig). Leer: keine Meldungen',
  ],
  'discord.support_channel_id': [
    'Support-Kanal',
    'Kanal-ID auf dem Plattform-Server. Jeder Support-Fall bekommt dort einen privaten Thread. Leer: aus',
  ],
  'discord.support_add_reporters': [
    'Meldende Personen in den Thread',
    'an: Wer einen Fall meldet, kommt mit verknüpftem Discord in den Thread (wer nicht auf dem Server ist, bekommt eine Einladung). aus: Das Team fügt Personen selbst hinzu',
  ],
  'discord.changelog_channel_id': [
    'Changelog-Kanal',
    'Kanal-ID für die Release Notes von Hubra und jedem Plugin-Update. Gewählt: Hubras Release Notes kommen hierhin statt ins Plattform-Log. Leer: aus',
  ],
  'discord.language': [
    'Sprache des Bots',
    'Sprache von allem, was der Bot auf dem Discord-Server der Plattform schreibt: Log, Audit, Warnungen, Tagesübersicht, Knöpfe, Antworten auf Befehle und Support-Threads. Vereinsserver folgen der Sprache des Vereins',
  ],
  'discord.audit_channel_id': [
    'Audit-Kanal',
    'Kanal-ID für jeden Eintrag im Audit-Log, mit Links in manage. Warnungen bleiben im Plattform-Log. Leer: aus',
  ],
}

// German labels of the plain groups in settings/, for a field shown elsewhere.
const GROUP_DE: Record<string, [string, string]> = Object.assign(
  {},
  ...Object.values(SETTINGS_GROUPS).map((g) => g.de ?? {}),
)

/**
 * One group of platform settings (not of one club), shown on the page it
 * belongs to: the mail relay under Mail, the backup storage under Backups,
 * plan limits under All clubs, and so on. Each section saves on its own.
 */
export function SettingsSection({ section }: { section: SettingsSectionId }) {
  const group = SETTINGS_GROUPS[section]
  const sectionKeys = group?.keys ?? SECTION_KEYS[section as OwnSectionId] ?? []
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
      sectionKeys.includes(s.key) &&
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
  const changelogChannel =
    draft['discord.changelog_channel_id'] ?? byKey['discord.changelog_channel_id']?.value ?? ''
  const manageUrl = byKey['alerts.manage_url']?.value ?? ''

  const rolesOn =
    (draft['discord.platform_roles'] ?? byKey['discord.platform_roles']?.value) === 'on'
  const supportChannel =
    draft['discord.support_channel_id'] ?? byKey['discord.support_channel_id']?.value ?? ''
  const botAddLink = clientId ? (
    <Anchor
      href={`https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(clientId)}&scope=bot&permissions=${(LOG_BOT_PERMISSIONS | (rolesOn ? MANAGE_ROLES : 0)) + (supportChannel ? THREAD_PERMISSIONS : 0)}`}
      target="_blank"
      rel="noreferrer"
    >
      {tr('Bot zum Plattform-Server hinzufügen', 'Add the bot to the platform server')}
    </Anchor>
  ) : (
    <Text span size="sm" c="dimmed">
      {tr(
        'Zuerst die Discord-Anwendungs-ID unter Einstellungen eintragen.',
        'Set the Discord application ID under Settings first.',
      )}
    </Text>
  )

  const field = (key: string) => {
    const s = byKey[key]
    if (!s) return null
    const de = FIELD_DE[key] ?? GROUP_DE[key]
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
    if (key === 'discord.language') {
      return (
        <Stack key={key} gap={4}>
          <Text size="sm" fw={500} component="div">
            {label}
          </Text>
          <SegmentedControl
            w="fit-content"
            value={(draft[key] ?? s.value) === 'en' ? 'en' : 'de'}
            onChange={(value) => setDraft((d) => ({ ...d, [key]: value }))}
            data={[
              { value: 'de', label: 'Deutsch' },
              { value: 'en', label: 'English' },
            ]}
          />
          <Text size="xs" c="dimmed">
            {common.description}
          </Text>
        </Stack>
      )
    }
    if (key === 'stripe.mode') {
      return (
        <Stack key={key} gap={4}>
          <Text size="sm" fw={500} component="div">
            {label}
          </Text>
          <SegmentedControl
            w="fit-content"
            value={(draft[key] ?? s.value) === 'live' ? 'live' : 'sandbox'}
            onChange={(value) => setDraft((d) => ({ ...d, [key]: value }))}
            color={(draft[key] ?? s.value) === 'live' ? 'red' : 'yellow'}
            data={[
              { value: 'sandbox', label: tr('Sandbox (Test)', 'Sandbox (test)') },
              { value: 'live', label: tr('Live (echtes Geld)', 'Live (real money)') },
            ]}
          />
          <Text size="xs" c="dimmed">
            {common.description}
          </Text>
        </Stack>
      )
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

          {section === 'performance' && byKey['errors.auto_resolve'] && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Fehler', 'Errors')}</Title>
                {resetButton(ERRORS)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Für Diagnose › Fehler. Von Hand als behoben markieren geht dort immer.',
                  'For Diagnostics › Errors. Marking an error fixed by hand always works there.',
                )}
              </Text>
              <Switch
                label={tr('Beim Upgrade als behoben markieren', 'Mark fixed on upgrade')}
                description={tr(
                  'Wenn alle Prozesse eine neue Version laufen, gelten offene Fehler, die dort nicht aufgetreten sind, als behoben. Kommen sie wieder, sind sie wieder offen.',
                  'Once every process runs a new build, open errors that did not happen on it count as fixed. If they come back, they are open again.',
                )}
                checked={(draft['errors.auto_resolve'] ?? byKey['errors.auto_resolve'].value) === 'on'}
                onChange={(e) => {
                  const on = e.currentTarget.checked
                  setDraft((d) => ({ ...d, 'errors.auto_resolve': on ? 'on' : 'off' }))
                }}
              />
            </Paper>
          )}

          {section === 'performance' && byKey['upgrades.post_deploy_steps'] && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Nach dem Deploy', 'After a deploy')}</Title>
                {resetButton(UPGRADES)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Das Ergebnis steht unter Diagnose › Systemzustand › Builds. Von Hand starten geht dort immer.',
                  'The result is under Diagnostics › System health › Builds. Starting them by hand always works there.',
                )}
              </Text>
              <Switch
                label={tr('Schritte nach dem Deploy selbst ausführen', 'Run the post-deploy steps')}
                description={tr(
                  'Sobald alle Prozesse eine neue Version laufen: flask db upgrade, sync-tenant-schemas, sync-permissions, seed und plugins sync, einmal pro Version.',
                  'Once every process runs a new build: flask db upgrade, sync-tenant-schemas, sync-permissions, seed and plugins sync, once per build.',
                )}
                checked={
                  (draft['upgrades.post_deploy_steps'] ?? byKey['upgrades.post_deploy_steps'].value) === 'on'
                }
                onChange={(e) => {
                  const on = e.currentTarget.checked
                  setDraft((d) => ({ ...d, 'upgrades.post_deploy_steps': on ? 'on' : 'off' }))
                }}
              />
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

          {group && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{group.title()}</Title>
                {resetButton(group.keys)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {group.desc()}
              </Text>
              <Stack gap="sm">{group.keys.map(field)}</Stack>
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
                  'Die Limits stehen bei jedem Tarif (oben). Am Mitgliederlimit läuft eine Kulanzfrist: Neue Mitglieder kommen noch dazu, die Admins sehen, welcher Tarif passt, und wechseln mit einem Klick. Danach kommt niemand Neues dazu (Einladungen, Anträge); Plattform-Staff kann in manage trotzdem hinzufügen. Mails pro Monat und Speicher werden nur gemeldet, nichts wird gesperrt. Einzelne Vereine bekommen eigene Limits auf ihrer Seite.',
                  'The limits are on each plan (above). At the member limit a grace period runs: new members still join, the admins see which plan fits and switch in one click. After it nobody new can join (invites, applications); platform staff can still add people in manage. Mails per month and storage are only reported, nothing is blocked. A club gets its own limits on its page.',
                )}
              </Text>
              <Stack gap="md">
                {field('limits.warn_percent')}
                {field('limits.grace_days')}
              </Stack>
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
                    {
                      label: tr('Changelog-Kanal (optional)', 'Changelog channel (optional)'),
                      description: tr(
                        'Gewählt: Die Release Notes jeder neuen Hubra-Version und jedes Plugin-Updates gehen hierhin. Leer: aus. Vereine wählen ihren eigenen Kanal in ihren Discord-Einstellungen.',
                        'Picked: the release notes of every new Hubra version and every plugin update go here. Empty: off. Clubs pick their own channel in their Discord settings.',
                      ),
                      channelId: changelogChannel,
                      onChange: (id) =>
                        setDraft((d) => ({ ...d, 'discord.changelog_channel_id': id })),
                      fallback: field('discord.changelog_channel_id'),
                      suggestedName: 'changelog',
                    },
                  ]}
                />
                {field('discord.language')}
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

          {section === 'discord-channels' && byKey['discord.support_channel_id'] && (
            <Paper withBorder p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Support-Threads', 'Support threads')}</Title>
                {resetButton(DISCORD_SUPPORT)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Jeder Support-Fall bekommt einen privaten Thread im Support-Kanal. Was dort geschrieben wird, kommt als Kommentar zum Fall (vom Team als Antwort, mit // am Anfang als interne Notiz), und Antworten aus manage und von der Support-Seite gehen in den Thread. Braucht den Message-Content-Intent der Discord-Anwendung (Developer Portal › Bot) und für den Bot im Kanal: Threads verwalten, private Threads erstellen, Nachrichten in Threads senden, Nachrichtenverlauf lesen, Einladung erstellen.',
                  'Every support case gets a private thread in the support channel. What is written there becomes a comment on the case (from the team as an answer, starting with // as an internal note), and answers from manage and the support site go into the thread. Needs the Discord application’s Message Content intent (Developer Portal › Bot) and, for the bot in the channel: Manage Threads, Create Private Threads, Send Messages in Threads, Read Message History, Create Invite.',
                )}
              </Text>
              <Stack gap="sm">
                <DiscordLogPicker
                  botTokenSet={!!byKey['discord.bot_token']?.isSet}
                  addLink={botAddLink}
                  slots={[
                    {
                      label: tr('Support-Kanal', 'Support channel'),
                      description: tr(
                        'Leer: keine Threads.',
                        'Empty: no threads.',
                      ),
                      channelId: supportChannel,
                      onChange: (id) => setDraft((d) => ({ ...d, 'discord.support_channel_id': id })),
                      fallback: field('discord.support_channel_id'),
                      suggestedName: 'hubra-support',
                      threads: true,
                    },
                  ]}
                />
                {field('discord.support_add_reporters')}
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
