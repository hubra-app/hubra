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
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import { ThemeSwitch } from '@hubra/ui'
import { LoadFailed } from '@/components/LoadFailed'
import { getLang, setLang, themeLabels, tr, useLang } from '@/lang'
import * as authApi from '@/api/auth'
import { TwoFactorTab } from './TwoFactor'
import { NotificationsTab } from './NotificationsTab'

const TABS = [
  { value: 'profil', label: () => tr('Profil', 'Profile') },
  { value: 'email', label: () => tr('E-Mail', 'Email') },
  { value: 'passwort', label: () => tr('Passwort', 'Password') },
  { value: 'zwei-faktor', label: () => tr('Zwei-Faktor', 'Two-factor') },
  { value: 'einstellungen', label: () => tr('Einstellungen', 'Settings') },
  { value: 'sitzungen', label: () => tr('Sitzungen', 'Sessions') },
  { value: 'benachrichtigungen', label: () => tr('Benachrichtigungen', 'Notifications') },
  { value: 'verknuepfungen', label: () => tr('Verknüpfungen', 'Linked accounts') },
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
  // Re-render when the language changes on the settings tab.
  useLang()
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

  if (profile.isError)
    return (
      <Center h="100vh">
        <LoadFailed onRetry={() => profile.refetch()} />
      </Center>
    )
  if (!profile.data)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  return (
    <SignedInFrame width={640}>
      <Title order={1} fz={30} mb={6}>
        {tr('Mein Konto', 'My account')}
      </Title>
      <Text c="dimmed" mb="lg">
        {tr(
          'Gilt für alle deine Vereine. Mitgliedschaft und Vereins-Mail findest du im jeweiligen Verein.',
          'Applies to all your clubs. Membership and club mail are in each club.',
        )}
      </Text>
      <Tabs value={tab} onChange={(v) => v && navigate(`/account/${v}`)} keepMounted={false}>
        <Tabs.List mb="lg" style={{ flexWrap: 'nowrap', overflowX: 'auto' }}>
          {TABS.map((t) => (
            <Tabs.Tab key={t.value} value={t.value}>
              {t.label()}
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
        <Tabs.Panel value="zwei-faktor">
          <TwoFactorTab />
        </Tabs.Panel>
        <Tabs.Panel value="einstellungen">
          <SettingsTab profile={profile.data} />
        </Tabs.Panel>
        <Tabs.Panel value="sitzungen">
          <SessionsTab />
        </Tabs.Panel>
        <Tabs.Panel value="benachrichtigungen">
          <NotificationsTab />
        </Tabs.Panel>
        <Tabs.Panel value="verknuepfungen">
          <LinkedAccountsTab />
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
    onError: (err) =>
      notify('error', tr('Speichern fehlgeschlagen', 'Saving failed'), errorText(err, '')),
  })
}

function ProfileTab({ profile }: { profile: authApi.Profile }) {
  const [name, setName] = useState(profile.name)
  const [color, setColor] = useState(profile.avatarColor)
  const [note, setNote] = useState(profile.profileNote ?? '')
  const save = useSaveProfile(tr('Profil gespeichert', 'Profile saved'))

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
            label={tr('Name', 'Name')}
            required
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <ColorInput
            label={tr('Avatar-Farbe', 'Avatar colour')}
            format="hex"
            value={color}
            onChange={setColor}
            eyeDropperButtonProps={{
              'aria-label': tr('Farbe vom Bildschirm wählen', 'Pick a colour from the screen'),
            }}
          />
          <Textarea
            label={tr('Über mich', 'About me')}
            description={tr(
              'Sichtbar für die Mitglieder deiner Vereine',
              'Visible to the members of your clubs',
            )}
            autosize
            minRows={3}
            maxLength={5000}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button type="submit" loading={save.isPending}>
              {tr('Speichern', 'Save')}
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
        tr('Adresse geändert', 'Address changed'),
        next.required
          ? tr(
              `Bestätige sie mit dem Link, den wir an ${next.email} gesendet haben.`,
              `Confirm it with the link we sent to ${next.email}.`,
            )
          : '',
      )
    },
    onError: (err) => setError(errorText(err, tr('Ändern fehlgeschlagen', 'Change failed'))),
  })
  const resend = useMutation({
    mutationFn: authApi.sendVerificationEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-verification'] })
      notify(
        'success',
        tr('Link gesendet', 'Link sent'),
        tr('Schau in deinem Posteingang nach.', 'Check your inbox.'),
      )
    },
    onError: (err) =>
      notify('error', tr('Senden fehlgeschlagen', 'Sending failed'), errorText(err, '')),
  })

  if (status.isError) return <LoadFailed onRetry={() => status.refetch()} />
  if (!status.data) return <Loader size="sm" />
  const s = status.data

  return (
    <Stack gap="md">
      <Paper withBorder radius="md" p="lg">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <div style={{ minWidth: 0 }}>
            <Text size="sm" c="dimmed">
              {tr(
                'Deine Adresse für die Anmeldung und alle Mails von Hubra',
                'Your address for signing in and all mail from Hubra',
              )}
            </Text>
            <Text fw={600} truncate>
              {s.email}
            </Text>
          </div>
          {s.verified ? (
            <Badge color="green" variant="light">
              {tr('Bestätigt', 'Confirmed')}
            </Badge>
          ) : (
            <Badge color="yellow" variant="light">
              {tr('Nicht bestätigt', 'Not confirmed')}
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
            {tr('Bestätigungslink senden', 'Send confirmation link')}
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
            <Title order={4}>{tr('Adresse ändern', 'Change address')}</Title>
            {error && (
              <Alert color="red" variant="light">
                {error}
              </Alert>
            )}
            <TextInput
              label={tr('Neue E-Mail-Adresse', 'New email address')}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
            />
            <PasswordInput
              label={tr('Aktuelles Passwort', 'Current password')}
              required
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
            />
            <Text size="xs" c="dimmed">
              {tr(
                'Die neue Adresse musst du danach bestätigen.',
                'You confirm the new address afterwards.',
              )}
            </Text>
            <Group justify="flex-end">
              <Button type="submit" loading={change.isPending}>
                {tr('Adresse ändern', 'Change address')}
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
      notify(
        'success',
        tr('Passwort geändert', 'Password changed'),
        tr('Es gilt ab sofort für alle deine Vereine.', 'It applies to all your clubs right away.'),
      )
    },
    onError: (err) => setError(errorText(err, tr('Ändern fehlgeschlagen', 'Change failed'))),
  })

  return (
    <Paper withBorder radius="md" p="lg">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (next !== repeat) {
            setError(
              tr(
                'Die beiden neuen Passwörter stimmen nicht überein.',
                'The two new passwords do not match.',
              ),
            )
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
            label={tr('Aktuelles Passwort', 'Current password')}
            required
            value={current}
            onChange={(e) => setCurrent(e.currentTarget.value)}
          />
          <PasswordInput
            label={tr('Neues Passwort', 'New password')}
            description={tr('Mindestens 12 Zeichen', 'At least 12 characters')}
            required
            value={next}
            onChange={(e) => setNext(e.currentTarget.value)}
          />
          <PasswordInput
            label={tr('Neues Passwort wiederholen', 'Repeat the new password')}
            required
            value={repeat}
            onChange={(e) => setRepeat(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button type="submit" loading={change.isPending}>
              {tr('Passwort ändern', 'Change password')}
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
  const save = useSaveProfile(tr('Einstellungen gespeichert', 'Settings saved'))
  return (
    <Paper withBorder radius="md" p="lg">
      <Stack gap="xs">
        <Text fw={600}>{tr('Sprache', 'Language')}</Text>
        <Text size="sm" c="dimmed">
          {tr(
            'Für Hubra und für die Mails, die du bekommst. Was ein Verein nur für sich einstellt, findest du in den Einstellungen des Vereins.',
            'For Hubra and the mail you get. What a club sets only for itself is in that club’s settings.',
          )}
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
        <Text fw={600} mt="md">
          {tr('Darstellung', 'Appearance')}
        </Text>
        <Text size="sm" c="dimmed">
          {tr(
            'Hell, dunkel oder wie dein Gerät. Gilt für Anmeldung, Vereine und Verwaltung, auf allen deinen Geräten.',
            'Light, dark or like your device. For sign-in, your clubs and the manager portal, on all your devices.',
          )}
        </Text>
        <Group mt="xs">
          <ThemeSwitch labels={themeLabels(tr)} />
        </Group>
      </Stack>
    </Paper>
  )
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString(getLang() === 'en' ? 'en-GB' : 'de-CH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function SessionsTab() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: ['sessions'], queryFn: authApi.getSessions })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['sessions'] })

  const revoke = useMutation({
    mutationFn: authApi.revokeSession,
    onSuccess: refresh,
    onError: (err) =>
      notify('error', tr('Abmelden fehlgeschlagen', 'Sign-out failed'), errorText(err, '')),
  })
  const revokeOthers = useMutation({
    mutationFn: authApi.revokeOtherSessions,
    onSuccess: (r) => {
      refresh()
      notify(
        'success',
        tr('Überall abgemeldet', 'Signed out everywhere'),
        tr(`${r.revoked} Sitzung(en) beendet.`, `${r.revoked} session(s) ended.`),
      )
    },
    onError: (err) =>
      notify('error', tr('Abmelden fehlgeschlagen', 'Sign-out failed'), errorText(err, '')),
  })

  if (sessions.isError) return <LoadFailed onRetry={() => sessions.refetch()} />
  if (!sessions.data) return <Loader size="sm" />

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {tr('Wo du angemeldet bist', 'Where you are signed in')}
        </Text>
        <Button
          variant="light"
          color="red"
          size="xs"
          loading={revokeOthers.isPending}
          disabled={sessions.data.length === 0}
          onClick={() => revokeOthers.mutate()}
        >
          {tr('Überall sonst abmelden', 'Sign out everywhere else')}
        </Button>
      </Group>
      {sessions.data.length === 0 && (
        <Text size="sm" c="dimmed">
          {tr(
            'Keine Sitzungen gefunden. Anmeldungen von vor diesem Update erscheinen erst nach der nächsten Anmeldung.',
            'No sessions found. Sign-ins from before this update appear after the next sign-in.',
          )}
        </Text>
      )}
      {sessions.data.map((s) => (
        <Paper key={`${s.club?.slug ?? 'account'}-${s.id}`} withBorder radius="md" p="md">
          <Group justify="space-between" wrap="nowrap">
            <div style={{ minWidth: 0 }}>
              <Group gap="xs" wrap="nowrap">
                <Text fw={600} truncate>
                  {s.deviceName ||
                    [s.browserFamily, s.platform].filter(Boolean).join(tr(' auf ', ' on ')) ||
                    tr('Unbekanntes Gerät', 'Unknown device')}
                </Text>
                {s.current && (
                  <Badge size="sm" variant="light">
                    {tr('Diese Sitzung', 'This session')}
                  </Badge>
                )}
              </Group>
              <Text size="xs" c="dimmed" truncate>
                {s.club?.name ?? tr('Konto (Anmeldeportal)', 'Account (sign-in portal)')} ·{' '}
                {s.ipAddress || tr('IP unbekannt', 'IP unknown')} ·{' '}
                {tr('zuletzt aktiv', 'last active')} {formatTime(s.lastActiveAt)}
              </Text>
            </div>
            {!s.current && (
              <Button
                variant="subtle"
                color="red"
                size="xs"
                style={{ flexShrink: 0 }}
                loading={revoke.isPending && revoke.variables === s}
                onClick={() => revoke.mutate(s)}
              >
                {tr('Abmelden', 'Sign out')}
              </Button>
            )}
          </Group>
        </Paper>
      ))}
    </Stack>
  )
}

const LINK_ERRORS: Record<string, () => string> = {
  expired: () =>
    tr(
      'Abgelaufen oder in einem anderen Browser gestartet. Bitte nochmals verknüpfen.',
      'Expired or started in another browser. Please link again.',
    ),
  cancelled: () => tr('Abgebrochen.', 'Cancelled.'),
  signin: () => tr('Bitte melde dich an und versuche es nochmals.', 'Please sign in and try again.'),
  taken: () =>
    tr(
      'Dieses Konto ist bereits mit einem anderen Hubra-Konto verknüpft.',
      'This account is already linked to another Hubra account.',
    ),
  failed: () => tr('Verknüpfen fehlgeschlagen.', 'Linking failed.'),
}

/**
 * Outside accounts the person links themselves (Discord), so a club's
 * Discord bot can recognise them and give them their roles. Only the
 * account's id and name are kept.
 */
function LinkedAccountsTab() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const linked = useQuery({ queryKey: ['linked-accounts'], queryFn: authApi.getLinkedAccounts })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['linked-accounts'] })

  useEffect(() => {
    const error = params.get('error')
    if (params.get('linked')) {
      notify('success', tr('Konto verknüpft', 'Account linked'))
    } else if (error) {
      notify('error', tr('Nicht verknüpft', 'Not linked'), (LINK_ERRORS[error] ?? LINK_ERRORS.failed)())
    } else {
      return
    }
    setParams({}, { replace: true })
  }, [params, setParams, notify])

  const start = useMutation({
    mutationFn: authApi.startLinkAccount,
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (err) => notify('error', tr('Nicht verknüpft', 'Not linked'), errorText(err, '')),
  })
  const unlink = useMutation({
    mutationFn: authApi.unlinkAccount,
    onSuccess: () => {
      refresh()
      notify('success', tr('Verknüpfung entfernt', 'Link removed'))
    },
    onError: (err) => notify('error', tr('Entfernen fehlgeschlagen', 'Removing failed'), errorText(err, '')),
  })

  if (linked.isError) return <LoadFailed onRetry={() => linked.refetch()} />
  if (!linked.data) return <Loader size="sm" />

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {tr(
          'Verknüpfe Konten bei anderen Diensten, damit deine Vereine dich dort erkennen, zum Beispiel für deine Rollen auf ihrem Discord-Server. Gespeichert werden nur der Name und die Nummer des Kontos.',
          'Link accounts on other services so your clubs recognise you there, for example for your roles on their Discord server. Only the account name and number are kept.',
        )}
      </Text>
      {linked.data.providers.map((p) => {
        const acc = linked.data.accounts.find((a) => a.provider === p.code)
        return (
          <Paper key={p.code} withBorder radius="md" p="md">
            <Group justify="space-between" wrap="nowrap">
              <div style={{ minWidth: 0 }}>
                <Text fw={600}>{p.name}</Text>
                <Text size="xs" c="dimmed" truncate>
                  {acc
                    ? tr(`Verknüpft als ${acc.username}`, `Linked as ${acc.username}`)
                    : p.available
                      ? tr('Nicht verknüpft', 'Not linked')
                      : tr('Auf dieser Plattform nicht eingerichtet', 'Not set up on this platform')}
                </Text>
              </div>
              {acc ? (
                <Button
                  variant="subtle"
                  color="red"
                  size="xs"
                  style={{ flexShrink: 0 }}
                  loading={unlink.isPending}
                  onClick={() => unlink.mutate(p.code)}
                >
                  {tr('Entfernen', 'Remove')}
                </Button>
              ) : (
                <Button
                  size="xs"
                  style={{ flexShrink: 0 }}
                  disabled={!p.available}
                  loading={start.isPending}
                  onClick={() => start.mutate(p.code)}
                >
                  {tr('Verknüpfen', 'Link')}
                </Button>
              )}
            </Group>
          </Paper>
        )
      })}
    </Stack>
  )
}
