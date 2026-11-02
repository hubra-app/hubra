import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { PageHead, Tabs } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import { planLabel } from '@/labels'
import { PlatformTranslations } from '@/screens/platform/Translations'
import { PlatformEncryption } from '@/screens/platform/Encryption'
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

const DISCORD_LOG = ['discord.log_channel_id', 'discord.audit_channel_id', 'discord.log_events']
// Defaults built into Hubra, not read from the environment.
const PERF = ['perf.slow_request_ms', 'perf.slow_query_ms', 'perf.p95_warning_ms']
const PLANS = ['starter', 'growth', 'enterprise'] as const
const LIMIT_KINDS = ['members', 'mail_month', 'storage_mb'] as const
const LIMITS = [
  'limits.warn_percent',
  ...PLANS.flatMap((p) => LIMIT_KINDS.map((k) => `limits.${p}.${k}`)),
]
const PRICES = PLANS.map((p) => `billing.price.${p}`)
const BUILT_IN = ['alerts.cooldown_minutes', 'alerts.retention_days', ...PERF, ...LIMITS]
const ALERTS = ['alerts.cooldown_minutes', 'alerts.retention_days', 'alerts.manage_url']

// Categories of platform events the bot posts (services/platform_discord.py).
const LOG_CATEGORIES: [string, string, string][] = [
  [
    'clubs',
    'Vereine erstellt, geändert, gesperrt, gelöscht; Module; Domains',
    'Clubs created, changed, suspended, deleted; modules; domains',
  ],
  [
    'requests',
    'Vereinsanfragen eingereicht, angenommen, abgelehnt',
    'Club requests submitted, approved, rejected',
  ],
  [
    'access',
    'Plattformrollen, Vereinsinhaber/-admins, Impersonation',
    'Platform roles, club owners/admins, impersonation',
  ],
  [
    'members',
    'Mitglieder kommen zu einem Verein (viele Meldungen)',
    'Members joining a club (many posts)',
  ],
  [
    'plugins',
    'Plugins installiert, aktualisiert, entfernt; Quellen',
    'Plugins installed, updated, removed; repositories',
  ],
  [
    'backups',
    'Backups erstellt, geprüft, wiederhergestellt, gelöscht',
    'Backups created, verified, restored, deleted',
  ],
  [
    'platform',
    'Plattform-Einstellungen, Schlüssel, Mailserver, Übersetzungen',
    'Platform settings, keys, mail server, translations',
  ],
  [
    'alerts',
    'Systemwarnungen: fehlgeschlagene Tasks, Fehlerrate, Infrastruktur',
    'System alerts: failed tasks, error rate, infrastructure',
  ],
]

// View Channel + Send Messages + Embed Links
const LOG_BOT_PERMISSIONS = (1 << 10) | (1 << 11) | (1 << 14)

const TABS = [
  'mail',
  'sender',
  'backups',
  'discord',
  'alerts',
  'limits',
  'prices',
  'encryption',
  'translations',
] as const
type Tab = (typeof TABS)[number]

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

export function PlatformSettings() {
  const { notify } = useAdmin()
  const { tr } = useLang()
  const queryClient = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()
  const last = location.pathname.split('/').pop() as Tab
  const tab: Tab = TABS.includes(last) ? last : 'mail'
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
  // A secret field left empty keeps the stored value.
  const changed = settings.filter((s) =>
    s.secret ? !!draft[s.key] : s.key in draft && draft[s.key] !== s.value,
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

  const logEvents = (draft['discord.log_events'] ?? byKey['discord.log_events']?.value ?? '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean)
  const clientId = byKey['discord.client_id']?.value ?? ''
  const logChanged = changed.some((s) => DISCORD_LOG.includes(s.key))
  const logChannel =
    draft['discord.log_channel_id'] ?? byKey['discord.log_channel_id']?.value ?? ''
  const auditChannel =
    draft['discord.audit_channel_id'] ?? byKey['discord.audit_channel_id']?.value ?? ''
  const manageUrl = byKey['alerts.manage_url']?.value ?? ''

  const botAddLink =
    clientId ? (
      <Anchor
        href={`https://discord.com/oauth2/authorize?client_id=${encodeURIComponent(clientId)}&scope=bot&permissions=${LOG_BOT_PERMISSIONS}`}
        target="_blank"
        rel="noreferrer"
      >
        {tr(
          'Bot zum Plattform-Server hinzufügen',
          'Add the bot to the platform server',
        )}
      </Anchor>
    ) : (
      <Text span size="sm" c="dimmed">
        {tr(
          'Zuerst die Discord-Anwendungs-ID oben eintragen.',
          'Set the Discord application ID above first.',
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
      <PageHead
        title={tr('Plattform-Einstellungen', 'Platform settings')}
        desc={tr(
          'Gilt für die ganze Plattform, für alle Vereine.',
          'These apply to the whole platform, for every club.',
        )}
      />
      <Tabs
        tabs={[
          { id: 'mail', label: tr('Mail-Relay', 'Mail relay') },
          { id: 'sender', label: tr('Systemabsender', 'System sender') },
          { id: 'backups', label: tr('Backup-Speicher', 'Backup storage') },
          { id: 'discord', label: 'Discord' },
          { id: 'alerts', label: tr('Warnungen', 'Alerts') },
          { id: 'limits', label: tr('Limits', 'Limits') },
          { id: 'prices', label: tr('Preise', 'Prices') },
          { id: 'encryption', label: tr('Verschlüsselung', 'Encryption') },
          { id: 'translations', label: tr('Übersetzungen', 'Translations') },
        ]}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/platform/settings${id === 'mail' ? '' : '/' + id}`)}
      />

      {tab === 'translations' ? (
        <PlatformTranslations />
      ) : tab === 'encryption' ? (
        <PlatformEncryption />
      ) : isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : (
        <Stack gap={20} maw={720}>
          {tab === 'mail' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
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

          {tab === 'mail' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
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

          {tab === 'sender' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={12}>
                <Title order={3}>{tr('Systemabsender', 'System sender')}</Title>
                {resetButton(SENDER)}
              </Group>
              <Stack gap="sm">{SENDER.map(field)}</Stack>
            </Paper>
          )}

          {tab === 'alerts' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Warnungen', 'Alerts')}</Title>
                {resetButton(ALERTS)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Warnmails gehen an Plattform-Admins (Superadmins und Rollen mit Plattform-Einstellungen), nicht an Support. Jede Person wählt unter Plattform › Warnungen › Meine Warnungen, welche sie bekommt.',
                  'Alert mails go to platform admins (superadmins and roles with platform settings), not to Support. Each person picks which ones they get under Platform › Alerts › My alerts.',
                )}
              </Text>
              <Stack gap="sm">{ALERTS.map(field)}</Stack>
            </Paper>
          )}

          {tab === 'alerts' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Leistung', 'Performance')}</Title>
                {resetButton(PERF)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Grenzwerte für Plattform › Warnungen › Leistung. Gemessen werden nur Routenmuster und die Form der Abfragen, keine Pfade, Werte oder Personen.',
                  'Thresholds for Platform › Alerts › Performance. Only route patterns and query shapes are measured, no paths, values or people.',
                )}
              </Text>
              <Stack gap="sm">{PERF.map(field)}</Stack>
            </Paper>
          )}

          {tab === 'limits' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Limits pro Tarif', 'Limits per plan')}</Title>
                {resetButton(LIMITS)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Leer heisst kein Limit. Ist das Mitgliederlimit erreicht, kommt niemand Neues dazu (Einladungen, Anträge); Plattform-Staff kann in manage trotzdem hinzufügen. Mails pro Monat und Speicher werden nur gemeldet, nichts wird gesperrt. Einzelne Vereine bekommen eigene Limits auf ihrer Seite unter Alle Vereine.',
                  'Empty means no limit. At the member limit nobody new can join (invites, applications); platform staff can still add people in manage. Mails per month and storage are only reported, nothing is blocked. A club gets its own limits on its page under All clubs.',
                )}
              </Text>
              <Stack gap="md">
                {field('limits.warn_percent')}
                <Table.ScrollContainer minWidth={520}>
                  <Table verticalSpacing={6}>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>{tr('Tarif', 'Plan')}</Table.Th>
                        <Table.Th>{tr('Mitglieder', 'Members')}</Table.Th>
                        <Table.Th>{tr('Mails pro Monat', 'Mails per month')}</Table.Th>
                        <Table.Th>{tr('Speicher (MB)', 'Storage (MB)')}</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {PLANS.map((p) => (
                        <Table.Tr key={p}>
                          <Table.Td fw={600}>{planLabel(p, tr)}</Table.Td>
                          {LIMIT_KINDS.map((k) => {
                            const key = `limits.${p}.${k}`
                            return (
                              <Table.Td key={k}>
                                <TextInput
                                  aria-label={`${planLabel(p, tr)}: ${k}`}
                                  inputMode="numeric"
                                  placeholder={tr('kein Limit', 'no limit')}
                                  value={draft[key] ?? byKey[key]?.value ?? ''}
                                  onChange={(e) => {
                                    const value = e.currentTarget.value
                                    setDraft((d) => ({ ...d, [key]: value }))
                                  }}
                                />
                              </Table.Td>
                            )
                          })}
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              </Stack>
            </Paper>
          )}

          {tab === 'prices' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Preise pro Tarif', 'Prices per plan')}</Title>
                {resetButton(PRICES)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Listenpreis pro Monat in CHF. Er wird nur in manage gezeigt, es wird noch nichts verrechnet. Ein Verein kann auf seiner Seite unter Alle Vereine einen eigenen Preis, Rabatt, Sponsor und bezahlte Zusatzmodule haben.',
                  'List price per month in CHF. It is only shown in manage; nothing is charged yet. A club can have its own price, discount, sponsor and paid add-ons on its page under All clubs.',
                )}
              </Text>
              <Table verticalSpacing={6}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{tr('Tarif', 'Plan')}</Table.Th>
                    <Table.Th>{tr('Preis pro Monat (CHF)', 'Price per month (CHF)')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {PLANS.map((p) => {
                    const key = `billing.price.${p}`
                    return (
                      <Table.Tr key={p}>
                        <Table.Td fw={600}>{planLabel(p, tr)}</Table.Td>
                        <Table.Td>
                          <TextInput
                            aria-label={`${planLabel(p, tr)}: CHF`}
                            inputMode="decimal"
                            placeholder={tr('kein Preis', 'no price')}
                            leftSection={<Text size="xs">CHF</Text>}
                            leftSectionWidth={44}
                            value={draft[key] ?? byKey[key]?.value ?? ''}
                            onChange={(e) => {
                              const value = e.currentTarget.value
                              setDraft((d) => ({ ...d, [key]: value }))
                            }}
                          />
                        </Table.Td>
                      </Table.Tr>
                    )
                  })}
                </Table.Tbody>
              </Table>
            </Paper>
          )}

          {tab === 'backups' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
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

          {tab === 'discord' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>Discord</Title>
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

          {tab === 'discord' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Plattform-Log', 'Platform log')}</Title>
                {resetButton(DISCORD_LOG)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Der Hubra-Bot meldet Plattform-Ereignisse auf dem Discord-Server der Plattform: neue Vereine und Anfragen, Rollen, Plugins, Backups, Einstellungen und Systemwarnungen. Mit einem Audit-Kanal gehen die Audit-Einträge dorthin und das Plattform-Log behält die Warnungen; jede Meldung kommt nur einmal. Braucht den Bot-Token oben.',
                  "The Hubra bot posts platform events on the platform's own Discord server: new clubs and requests, roles, plugins, backups, settings and system alerts. With an audit channel, audit entries go there and the platform log keeps the alerts; each post goes out once. Needs the bot token above.",
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
                        'Systemwarnungen, und alles Angehakte, solange es keinen Audit-Kanal gibt.',
                        'System alerts, and everything ticked while there is no audit channel.',
                      ),
                      channelId: logChannel,
                      onChange: (id) => setDraft((d) => ({ ...d, 'discord.log_channel_id': id })),
                      fallback: field('discord.log_channel_id'),
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
                    },
                  ]}
                />
                <Checkbox.Group
                  label={
                    <Group gap={6} component="span">
                      {tr('Was gemeldet wird', 'What is posted')}
                      {byKey['discord.log_events'] && (
                        <SourceBadge s={byKey['discord.log_events']} />
                      )}
                    </Group>
                  }
                  value={logEvents}
                  onChange={(v) =>
                    setDraft((d) => ({
                      ...d,
                      'discord.log_events': LOG_CATEGORIES.map(([c]) => c)
                        .filter((c) => v.includes(c))
                        .join(','),
                    }))
                  }
                >
                  <Stack gap={6} mt={6}>
                    {LOG_CATEGORIES.map(([id, de, en]) => (
                      <Checkbox key={id} value={id} label={tr(de, en)} />
                    ))}
                  </Stack>
                </Checkbox.Group>
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
                      onClick={() => navigate('/app/platform/settings/alerts')}
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

          <Group>
            <Button
              loading={saving}
              disabled={changed.length === 0}
              onClick={() => save(Object.fromEntries(changed.map((s) => [s.key, draft[s.key]])))}
            >
              {tr('Speichern', 'Save')}
            </Button>
          </Group>

          {tab === 'mail' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
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
