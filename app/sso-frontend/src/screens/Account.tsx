import { useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Center,
  ColorInput,
  Group,
  Loader,
  Paper,
  PasswordInput,
  SegmentedControl,
  Stack,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import { setLang } from '@/lang'
import * as authApi from '@/api/auth'

const TABS = [
  { value: 'profil', label: 'Profil' },
  { value: 'email', label: 'E-Mail' },
  { value: 'passwort', label: 'Passwort' },
  { value: 'einstellungen', label: 'Einstellungen' },
  { value: 'sitzungen', label: 'Sitzungen' },
] as const

type Tab = (typeof TABS)[number]['value']

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/**
 * The person's own account, the same for every club: profile, email,
 * password, language and the sessions of all their clubs. What belongs to
 * one club (membership, club address, mail forwarding) stays in that club.
 */
export function AccountScreen() {
  const { authStatus } = useSso()
  const navigate = useNavigate()
  const { tab: rawTab } = useParams()
  const tab: Tab = TABS.some((t) => t.value === rawTab) ? (rawTab as Tab) : 'profil'

  useEffect(() => {
    if (authStatus === 'anon') navigate('/login', { replace: true })
  }, [authStatus, navigate])

  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: authApi.getProfile,
    enabled: authStatus === 'authed',
  })

  if (!profile.data)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  return (
    <SignedInFrame width={640}>
      <Title order={1} fz={30} mb={6}>
        Mein Konto
      </Title>
      <Text c="dimmed" mb="lg">
        Gilt für alle deine Vereine. Mitgliedschaft und Vereins-Mail findest du im jeweiligen
        Verein.
      </Text>
      <Tabs value={tab} onChange={(v) => v && navigate(`/account/${v}`)} keepMounted={false}>
        <Tabs.List mb="lg" style={{ flexWrap: 'nowrap', overflowX: 'auto' }}>
          {TABS.map((t) => (
            <Tabs.Tab key={t.value} value={t.value}>
              {t.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        <Tabs.Panel value="profil">
          <ProfileTab profile={profile.data} />
        </Tabs.Panel>
        <Tabs.Panel value="email">
          <EmailTab />
        </Tabs.Panel>
        <Tabs.Panel value="passwort">
          <PasswordTab />
        </Tabs.Panel>
        <Tabs.Panel value="einstellungen">
          <SettingsTab profile={profile.data} />
        </Tabs.Panel>
        <Tabs.Panel value="sitzungen">
          <SessionsTab />
        </Tabs.Panel>
      </Tabs>
    </SignedInFrame>
  )
}

function useSaveProfile(success: string) {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: (p) => {
      queryClient.setQueryData(['profile'], p)
      notify('success', success)
    },
    onError: (err) => notify('error', 'Speichern fehlgeschlagen', errorText(err, '')),
  })
}

function ProfileTab({ profile }: { profile: authApi.Profile }) {
  const [name, setName] = useState(profile.name)
  const [color, setColor] = useState(profile.avatarColor)
  const [note, setNote] = useState(profile.profileNote ?? '')
  const save = useSaveProfile('Profil gespeichert')

  return (
    <Paper withBorder radius="md" p="lg">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate({ name, avatarColor: color, profileNote: note || null })
        }}
      >
        <Stack gap="md">
          <TextInput
            label="Name"
            required
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <ColorInput label="Avatar-Farbe" format="hex" value={color} onChange={setColor} />
          <Textarea
            label="Über mich"
            description="Sichtbar für die Mitglieder deiner Vereine"
            autosize
            minRows={3}
            maxLength={5000}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button type="submit" loading={save.isPending}>
              Speichern
            </Button>
          </Group>
        </Stack>
      </form>
    </Paper>
  )
}

function EmailTab() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const status = useQuery({
    queryKey: ['email-verification'],
    queryFn: ({ signal }) => authApi.getVerificationStatus(signal),
  })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const change = useMutation({
    mutationFn: () => authApi.changeEmail(email.trim().toLowerCase(), password),
    onSuccess: (next) => {
      queryClient.setQueryData(['email-verification'], next)
      queryClient.invalidateQueries({ queryKey: ['profile'] })
      setPassword('')
      setEmail('')
      setError('')
      notify(
        'success',
        'Adresse geändert',
        next.required ? `Bestätige sie mit dem Link, den wir an ${next.email} gesendet haben.` : '',
      )
    },
    onError: (err) => setError(errorText(err, 'Ändern fehlgeschlagen')),
  })
  const resend = useMutation({
    mutationFn: authApi.sendVerificationEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-verification'] })
      notify('success', 'Link gesendet', 'Schau in deinem Posteingang nach.')
    },
    onError: (err) => notify('error', 'Senden fehlgeschlagen', errorText(err, '')),
  })

  if (!status.data) return <Loader size="sm" />
  const s = status.data

  return (
    <Stack gap="md">
      <Paper withBorder radius="md" p="lg">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <div style={{ minWidth: 0 }}>
            <Text size="sm" c="dimmed">
              Deine Adresse für die Anmeldung und alle Mails von Hubra
            </Text>
            <Text fw={600} truncate>
              {s.email}
            </Text>
          </div>
          {s.verified ? (
            <Badge color="green" variant="light">
              Bestätigt
            </Badge>
          ) : (
            <Badge color="yellow" variant="light">
              Nicht bestätigt
            </Badge>
          )}
        </Group>
        {!s.verified && s.mailConfigured && (
          <Button
            mt="md"
            variant="light"
            loading={resend.isPending}
            onClick={() => resend.mutate()}
          >
            Bestätigungslink senden
          </Button>
        )}
      </Paper>

      <Paper withBorder radius="md" p="lg">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            change.mutate()
          }}
        >
          <Stack gap="md">
            <Title order={4}>Adresse ändern</Title>
            {error && (
              <Alert color="red" variant="light">
                {error}
              </Alert>
            )}
            <TextInput
              label="Neue E-Mail-Adresse"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
            />
            <PasswordInput
              label="Aktuelles Passwort"
              required
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
            />
            <Text size="xs" c="dimmed">
              Die neue Adresse musst du danach bestätigen.
            </Text>
            <Group justify="flex-end">
              <Button type="submit" loading={change.isPending}>
                Adresse ändern
              </Button>
            </Group>
          </Stack>
        </form>
      </Paper>
    </Stack>
  )
}

function PasswordTab() {
  const { notify } = useSso()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState('')

  const change = useMutation({
    mutationFn: () => authApi.changePassword(current, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setRepeat('')
      setError('')
      notify('success', 'Passwort geändert', 'Es gilt ab sofort für alle deine Vereine.')
    },
    onError: (err) => setError(errorText(err, 'Ändern fehlgeschlagen')),
  })

  return (
    <Paper withBorder radius="md" p="lg">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (next !== repeat) {
            setError('Die beiden neuen Passwörter stimmen nicht überein.')
            return
          }
          change.mutate()
        }}
      >
        <Stack gap="md">
          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}
          <PasswordInput
            label="Aktuelles Passwort"
            required
            value={current}
            onChange={(e) => setCurrent(e.currentTarget.value)}
          />
          <PasswordInput
            label="Neues Passwort"
            description="Mindestens 12 Zeichen"
            required
            value={next}
            onChange={(e) => setNext(e.currentTarget.value)}
          />
          <PasswordInput
            label="Neues Passwort wiederholen"
            required
            value={repeat}
            onChange={(e) => setRepeat(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button type="submit" loading={change.isPending}>
              Passwort ändern
            </Button>
          </Group>
        </Stack>
      </form>
    </Paper>
  )
}

const LANGUAGES = [
  { value: 'de-CH', label: 'Deutsch' },
  { value: 'en-GB', label: 'English' },
]

function SettingsTab({ profile }: { profile: authApi.Profile }) {
  const save = useSaveProfile('Einstellungen gespeichert')
  return (
    <Paper withBorder radius="md" p="lg">
      <Stack gap="xs">
        <Text fw={600}>Sprache</Text>
        <Text size="sm" c="dimmed">
          Für Hubra und für die Mails, die du bekommst. Was ein Verein nur für sich einstellt,
          findest du in den Einstellungen des Vereins.
        </Text>
        <SegmentedControl
          mt="xs"
          data={LANGUAGES}
          value={profile.language}
          disabled={save.isPending}
          onChange={(language) => {
            // The portal itself follows the account language straight away.
            setLang(language.startsWith('en') ? 'en' : 'de')
            save.mutate({ language })
          }}
        />
      </Stack>
    </Paper>
  )
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('de-CH', { dateStyle: 'medium', timeStyle: 'short' })
}

function SessionsTab() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: authApi.getSessions })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['sessions'] })

  const revoke = useMutation({
    mutationFn: (s: authApi.AccountSession) => authApi.revokeSession(s.club.slug, s.id),
    onSuccess: refresh,
    onError: (err) => notify('error', 'Abmelden fehlgeschlagen', errorText(err, '')),
  })
  const revokeOthers = useMutation({
    mutationFn: authApi.revokeOtherSessions,
    onSuccess: (r) => {
      refresh()
      notify('success', 'Überall abgemeldet', `${r.revoked} Sitzung(en) beendet.`)
    },
    onError: (err) => notify('error', 'Abmelden fehlgeschlagen', errorText(err, '')),
  })

  if (!sessions.data) return <Loader size="sm" />

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          Wo du in deinen Vereinen angemeldet bist
        </Text>
        <Button
          variant="light"
          color="red"
          size="xs"
          loading={revokeOthers.isPending}
          disabled={sessions.data.length === 0}
          onClick={() => revokeOthers.mutate()}
        >
          Überall sonst abmelden
        </Button>
      </Group>
      {sessions.data.length === 0 && (
        <Text size="sm" c="dimmed">
          Keine Sitzungen gefunden. Aufgeführt werden Anmeldungen in deinen Vereinen; Anmeldungen
          hier im Konto erscheinen noch nicht.
        </Text>
      )}
      {sessions.data.map((s) => (
        <Paper key={`${s.club.slug}-${s.id}`} withBorder radius="md" p="md">
          <Group justify="space-between" wrap="nowrap">
            <div style={{ minWidth: 0 }}>
              <Group gap="xs" wrap="nowrap">
                <Text fw={600} truncate>
                  {s.deviceName ||
                    [s.browserFamily, s.platform].filter(Boolean).join(' auf ') ||
                    'Unbekanntes Gerät'}
                </Text>
                {s.current && (
                  <Badge size="sm" variant="light">
                    Diese Sitzung
                  </Badge>
                )}
              </Group>
              <Text size="xs" c="dimmed" truncate>
                {s.club.name} · {s.ipAddress || 'IP unbekannt'} · zuletzt aktiv{' '}
                {formatTime(s.lastActiveAt)}
              </Text>
            </div>
            {!s.current && (
              <Button
                variant="subtle"
                color="red"
                size="xs"
                loading={revoke.isPending && revoke.variables?.id === s.id}
                onClick={() => revoke.mutate(s)}
              >
                Abmelden
              </Button>
            )}
          </Group>
        </Paper>
      ))}
    </Stack>
  )
}
