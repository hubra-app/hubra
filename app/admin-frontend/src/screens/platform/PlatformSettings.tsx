import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { PageHead, Tabs } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import { PlatformTranslations } from '@/screens/platform/Translations'
import {
  getPlatformSettings,
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
  'backup.s3.endpoint',
  'backup.s3.bucket',
  'backup.s3.region',
  'backup.s3.access_key',
  'backup.s3.secret_key',
]

const TABS = ['mail', 'sender', 'backups', 'translations'] as const
type Tab = (typeof TABS)[number]

function SourceBadge({ s }: { s: PlatformSetting }) {
  return s.source === 'platform' ? (
    <Badge size="xs" variant="light">
      {tr('Hier gesetzt', 'Set here')}
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
  'mail.relay.host': ['SMTP-Relay-Server', 'Ausgehender Mailserver für alle Mails, die Hubra verschickt'],
  'mail.relay.port': ['SMTP-Relay-Port', '587 für STARTTLS, 25 für ein internes Relay ohne TLS'],
  'mail.relay.user': ['SMTP-Benutzer', 'Leer lassen, wenn das Relay keine Anmeldung braucht'],
  'mail.relay.password': ['SMTP-Passwort', 'Wird verschlüsselt gespeichert'],
  'mail.fallback.host': [
    'Fallback-Relay-Server',
    'Wird genutzt, wenn das Relay eine Mail ablehnt, z. B. weil das Sendekontingent erreicht ist (smtp-relay.brevo.com). Leer lassen für keinen Fallback',
  ],
  'mail.fallback.port': ['Fallback-Relay-Port', '587 für STARTTLS, 465 für TLS'],
  'mail.fallback.user': ['Fallback-SMTP-Benutzer', 'Leer lassen, wenn der Fallback keine Anmeldung braucht'],
  'mail.fallback.password': ['Fallback-SMTP-Passwort', 'Wird verschlüsselt gespeichert'],
  'mail.system.sender_email': ['Absenderadresse des Systems', 'Absender für Anmelde-, SSO- und Plattform-Mails'],
  'mail.system.sender_name': ['Absendername des Systems', 'Angezeigter Name des Systemabsenders'],
  'backup.s3.endpoint': ['S3-Endpunkt', 'S3-kompatible Adresse, z. B. https://eu2.contabostorage.com'],
  'backup.s3.bucket': ['S3-Bucket', 'Bucket, in den die verschlüsselten Backups gehen'],
  'backup.s3.region': ['S3-Region', "Bei Contabo meist 'default'"],
  'backup.s3.access_key': ['S3-Access-Key', 'Wird verschlüsselt gespeichert'],
  'backup.s3.secret_key': ['S3-Secret-Key', 'Wird verschlüsselt gespeichert'],
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
      notify('error', tr('Testmail fehlgeschlagen', 'Test mail failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setTesting(null)
    }
  }

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
      <PasswordInput key={key} {...common} placeholder={s.isSet ? tr('•••••••• (unverändert)', '•••••••• (unchanged)') : ''} />
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
          { id: 'translations', label: tr('Übersetzungen', 'Translations') },
        ]}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(`/app/platform/settings${id === 'mail' ? '' : '/' + id}`)
        }
      />

      {tab === 'translations' ? (
        <PlatformTranslations />
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

          {tab === 'backups' && (
            <Paper withBorder shadow="sm" radius="lg" p="lg">
              <Group justify="space-between" mb={4}>
                <Title order={3}>{tr('Backup-Speicher', 'Backup storage')}</Title>
                {resetButton(BACKUP)}
              </Group>
              <Text size="xs" c="dimmed" mb={12}>
                {tr(
                  'Hierhin gehen das globale Backup und die Backups jedes Vereins, verschlüsselt mit BACKUP_PUBLIC_KEY aus der Umgebung.',
                  'The global backup and every club backup go here, encrypted with BACKUP_PUBLIC_KEY from env.',
                )}
              </Text>
              <Stack gap="sm">{BACKUP.map(field)}</Stack>
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
