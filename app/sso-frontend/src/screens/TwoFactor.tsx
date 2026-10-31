import { useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Code,
  CopyButton,
  Group,
  Loader,
  Paper,
  PasswordInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSso } from '@/context/SsoContext'
import { LoadFailed } from '@/components/LoadFailed'
import { tr } from '@/lang'
import * as authApi from '@/api/auth'
import { createPasskey, passkeyCancelled, passkeysSupported } from '@/webauthn'

function errorText(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/** The recovery codes, shown once, with copy and download. */
function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const text = codes.join('\n')
  const download = () => {
    const url = URL.createObjectURL(new Blob([`${text}\n`], { type: 'text/plain' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'hubra-wiederherstellungscodes.txt'
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <Stack gap="md">
      <Alert color="yellow" variant="light" title={tr('Codes jetzt sichern', 'Save these codes now')}>
        {tr(
          'Mit jedem Code kannst du dich einmal ohne App anmelden, zum Beispiel wenn du dein Handy verlierst. Sie werden nur jetzt angezeigt.',
          'Each code signs you in once without the app, for example if you lose your phone. They are shown only now.',
        )}
      </Alert>
      <SimpleGrid cols={2} spacing="xs">
        {codes.map((c) => (
          <Code key={c} fz="md" ta="center" py={6}>
            {c}
          </Code>
        ))}
      </SimpleGrid>
      <Group justify="space-between">
        <Group gap="xs">
          <CopyButton value={text}>
            {({ copied, copy }) => (
              <Button variant="default" onClick={copy}>
                {copied ? tr('Kopiert', 'Copied') : tr('Kopieren', 'Copy')}
              </Button>
            )}
          </CopyButton>
          <Button variant="default" onClick={download}>
            {tr('Herunterladen', 'Download')}
          </Button>
        </Group>
        <Button onClick={onDone}>{tr('Ich habe sie gesichert', 'I have saved them')}</Button>
      </Group>
    </Stack>
  )
}

/** Asks for the current password before a change, then runs *onConfirm*. */
function PasswordStep({
  label,
  color,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  label: string
  color?: string
  pending: boolean
  error: string
  onConfirm: (password: string) => void
  onCancel: () => void
}) {
  const [password, setPassword] = useState('')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onConfirm(password)
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
          autoFocus
          required
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onCancel}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" color={color} loading={pending}>
            {label}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '–'
}

/** A guess at a name for a new passkey, from the browser. */
function deviceName(): string {
  const ua = navigator.userAgent
  if (/iPhone/.test(ua)) return 'iPhone'
  if (/iPad/.test(ua)) return 'iPad'
  if (/Android/.test(ua)) return 'Android'
  if (/Mac OS X/.test(ua)) return 'Mac'
  if (/Windows/.test(ua)) return 'Windows'
  return 'Passkey'
}

type ShowCodes = (codes: string[]) => void

function PasskeysCard({ s, showCodes }: { s: authApi.MfaStatus; showCodes: ShowCodes }) {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<authApi.PasskeyInfo | null>(null)
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const supported = passkeysSupported()

  const add = useMutation({
    mutationFn: async () => {
      const start = await authApi.passkeyRegisterOptions(password)
      const credential = await createPasskey(start.options)
      return authApi.addPasskey(start.state, credential, name.trim() || deviceName())
    },
    onSuccess: ({ recoveryCodes, ...next }) => {
      queryClient.setQueryData(['mfa'], next)
      setAdding(false)
      setPassword('')
      notify('success', tr('Passkey hinzugefügt', 'Passkey added'))
      if (recoveryCodes.length) showCodes(recoveryCodes)
    },
    onError: (err) =>
      setError(
        passkeyCancelled(err)
          ? tr('Abgebrochen. Versuche es nochmals.', 'Cancelled. Please try again.')
          : errorText(err, tr('Fehlgeschlagen', 'Failed')),
      ),
  })
  const remove = useMutation({
    mutationFn: (pw: string) => authApi.removePasskey(removing!.id, pw),
    onSuccess: (next) => {
      queryClient.setQueryData(['mfa'], next)
      setRemoving(null)
      notify('success', tr('Passkey entfernt', 'Passkey removed'))
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })

  return (
    <Paper withBorder radius="md" p="lg">
      <Stack gap="md">
        <div>
          <Title order={3} fz="lg">
            {tr('Passkeys', 'Passkeys')}
          </Title>
          <Text size="sm" c="dimmed">
            {tr(
              'Melde dich mit Face ID, Fingerabdruck, der Geräte-PIN oder einem Sicherheitsschlüssel an, ohne Passwort. Passkeys lassen sich nicht abfischen.',
              'Sign in with Face ID, a fingerprint, the device PIN or a security key, without a password. Passkeys cannot be phished.',
            )}
          </Text>
        </div>

        {s.passkeys.map((p) => (
          <Group key={p.id} justify="space-between" wrap="nowrap">
            <div style={{ minWidth: 0 }}>
              <Text fw={600} truncate>
                {p.name}
              </Text>
              <Text size="xs" c="dimmed">
                {tr(
                  `Hinzugefügt ${formatDate(p.createdAt)} · zuletzt benutzt ${formatDate(p.lastUsedAt)}`,
                  `Added ${formatDate(p.createdAt)} · last used ${formatDate(p.lastUsedAt)}`,
                )}
              </Text>
            </div>
            <Button
              variant="subtle"
              color="red"
              size="xs"
              onClick={() => {
                setError('')
                setAdding(false)
                setRemoving(p)
              }}
            >
              {tr('Entfernen', 'Remove')}
            </Button>
          </Group>
        ))}

        {removing && (
          <PasswordStep
            label={tr(`«${removing.name}» entfernen`, `Remove “${removing.name}”`)}
            color="red"
            pending={remove.isPending}
            error={error}
            onConfirm={(pw) => remove.mutate(pw)}
            onCancel={() => setRemoving(null)}
          />
        )}

        {!s.passkeysAvailable && (
          <Text size="sm" c="dimmed">
            {tr(
              'Auf diesem Server sind Passkeys nicht eingerichtet (SSO_BASE_URL fehlt).',
              'Passkeys are not set up on this server (SSO_BASE_URL is missing).',
            )}
          </Text>
        )}
        {s.passkeysAvailable && !supported && (
          <Text size="sm" c="dimmed">
            {tr('Dieser Browser kann keine Passkeys.', 'This browser cannot use passkeys.')}
          </Text>
        )}

        {adding ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              setError('')
              add.mutate()
            }}
          >
            <Stack gap="md">
              {error && (
                <Alert color="red" variant="light">
                  {error}
                </Alert>
              )}
              <TextInput
                label={tr('Name', 'Name')}
                description={tr('Damit du ihn später erkennst', 'So you recognise it later')}
                placeholder={deviceName()}
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.currentTarget.value)}
              />
              <PasswordInput
                label={tr('Aktuelles Passwort', 'Current password')}
                required
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setAdding(false)}>
                  {tr('Abbrechen', 'Cancel')}
                </Button>
                <Button type="submit" loading={add.isPending}>
                  {tr('Weiter', 'Continue')}
                </Button>
              </Group>
            </Stack>
          </form>
        ) : (
          s.passkeysAvailable &&
          supported &&
          !removing && (
            <Group justify="flex-end">
              <Button
                onClick={() => {
                  setError('')
                  setName('')
                  setAdding(true)
                }}
              >
                {tr('Passkey hinzufügen', 'Add a passkey')}
              </Button>
            </Group>
          )
        )}
      </Stack>
    </Paper>
  )
}

type AppStep = 'idle' | 'start' | 'scan' | 'disable'

function AppCard({ s, showCodes }: { s: authApi.MfaStatus; showCodes: ShowCodes }) {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<AppStep>('idle')
  const [setup, setSetup] = useState<authApi.TotpSetup | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  const go = (next: AppStep) => {
    setError('')
    setStep(next)
  }
  const saved = (next: authApi.MfaStatus) => queryClient.setQueryData(['mfa'], next)

  const start = useMutation({
    mutationFn: authApi.startTotpSetup,
    onSuccess: (r) => {
      setSetup(r)
      setCode('')
      go('scan')
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  const enable = useMutation({
    mutationFn: () => authApi.enableTotp(code.trim()),
    onSuccess: ({ recoveryCodes, ...next }) => {
      saved(next)
      setSetup(null)
      go('idle')
      notify('success', tr('Authenticator-App ist an', 'Authenticator app is on'))
      if (recoveryCodes.length) showCodes(recoveryCodes)
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  const disable = useMutation({
    mutationFn: authApi.disableTotp,
    onSuccess: (next) => {
      saved(next)
      go('idle')
      notify('success', tr('Authenticator-App ist aus', 'Authenticator app is off'))
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })

  return (
    <Paper withBorder radius="md" p="lg">
      <Stack gap="md">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <div>
            <Title order={3} fz="lg">
              {tr('Authenticator-App', 'Authenticator app')}
            </Title>
            <Text size="sm" c="dimmed">
              {tr(
                'Beim Anmelden fragen wir nach dem Passwort zusätzlich einen Code aus einer App wie Google Authenticator, Microsoft Authenticator, 1Password oder Aegis.',
                'After your password, sign-in asks for a code from an app such as Google Authenticator, Microsoft Authenticator, 1Password or Aegis.',
              )}
            </Text>
          </div>
          <Badge color={s.totpEnabled ? 'green' : 'gray'} variant="light" style={{ flexShrink: 0 }}>
            {s.totpEnabled ? tr('An', 'On') : tr('Aus', 'Off')}
          </Badge>
        </Group>

        {step === 'idle' && (
          <Group justify="flex-end">
            {s.totpEnabled ? (
              <Button variant="light" color="red" onClick={() => go('disable')}>
                {tr('Ausschalten', 'Turn off')}
              </Button>
            ) : (
              <Button variant={s.passkeys.length ? 'default' : 'filled'} onClick={() => go('start')}>
                {tr('Einrichten', 'Set up')}
              </Button>
            )}
          </Group>
        )}

        {step === 'start' && (
          <PasswordStep
            label={tr('Weiter', 'Continue')}
            pending={start.isPending}
            error={error}
            onConfirm={(pw) => start.mutate(pw)}
            onCancel={() => go('idle')}
          />
        )}

        {step === 'scan' && setup && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              enable.mutate()
            }}
          >
            <Stack gap="md">
              <Text size="sm">
                {tr(
                  '1. Scanne den QR-Code mit deiner App. 2. Gib den 6-stelligen Code ein, den die App anzeigt.',
                  '1. Scan the QR code with your app. 2. Enter the 6-digit code the app shows.',
                )}
              </Text>
              <Group align="center" gap="lg" wrap="wrap">
                <img
                  src={`data:image/svg+xml;utf8,${encodeURIComponent(setup.qrSvg)}`}
                  alt={tr('QR-Code für die Authenticator-App', 'QR code for the authenticator app')}
                  width={180}
                  height={180}
                  style={{ background: '#fff', borderRadius: 8 }}
                />
                <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
                  <Text size="xs" c="dimmed">
                    {tr('Kein Scan möglich? Gib diesen Schlüssel ein:', "Can't scan? Enter this key:")}
                  </Text>
                  <Code style={{ wordBreak: 'break-all' }}>{setup.secret}</Code>
                </Stack>
              </Group>
              {error && (
                <Alert color="red" variant="light">
                  {error}
                </Alert>
              )}
              <TextInput
                label={tr('Code aus der App', 'Code from the app')}
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={7}
                required
                value={code}
                onChange={(e) => setCode(e.currentTarget.value)}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => go('idle')}>
                  {tr('Abbrechen', 'Cancel')}
                </Button>
                <Button type="submit" loading={enable.isPending}>
                  {tr('Einschalten', 'Turn on')}
                </Button>
              </Group>
            </Stack>
          </form>
        )}

        {step === 'disable' && (
          <PasswordStep
            label={tr('Ausschalten', 'Turn off')}
            color="red"
            pending={disable.isPending}
            error={error}
            onConfirm={(pw) => disable.mutate(pw)}
            onCancel={() => go('idle')}
          />
        )}
      </Stack>
    </Paper>
  )
}

function RecoveryCard({ s, showCodes }: { s: authApi.MfaStatus; showCodes: ShowCodes }) {
  const queryClient = useQueryClient()
  const [renewing, setRenewing] = useState(false)
  const [error, setError] = useState('')
  const renew = useMutation({
    mutationFn: authApi.renewRecoveryCodes,
    onSuccess: ({ recoveryCodes, ...next }) => {
      queryClient.setQueryData(['mfa'], next)
      setRenewing(false)
      showCodes(recoveryCodes)
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  return (
    <Paper withBorder radius="md" p="lg">
      <Stack gap="md">
        <div>
          <Title order={3} fz="lg">
            {tr('Wiederherstellungscodes', 'Recovery codes')}
          </Title>
          <Text size="sm" c={s.recoveryCodesLeft <= 3 ? 'orange' : 'dimmed'}>
            {tr(
              `Noch ${s.recoveryCodesLeft} von 10 übrig. Jeder Code ersetzt einmal die App oder den Passkey.`,
              `${s.recoveryCodesLeft} of 10 left. Each code stands in once for the app or a passkey.`,
            )}
          </Text>
        </div>
        {renewing ? (
          <PasswordStep
            label={tr('Neue Codes erstellen', 'Create new codes')}
            pending={renew.isPending}
            error={error}
            onConfirm={(pw) => renew.mutate(pw)}
            onCancel={() => setRenewing(false)}
          />
        ) : (
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setError('')
                setRenewing(true)
              }}
            >
              {tr('Neue Codes erstellen', 'Create new codes')}
            </Button>
          </Group>
        )}
      </Stack>
    </Paper>
  )
}

export function TwoFactorTab() {
  const status = useQuery({ queryKey: ['mfa'], queryFn: authApi.getMfa })
  const [codes, setCodes] = useState<string[]>([])

  if (status.isError) return <LoadFailed onRetry={() => status.refetch()} />
  if (!status.data) return <Loader size="sm" />
  const s = status.data

  if (codes.length)
    return (
      <Paper withBorder radius="md" p="lg">
        <RecoveryCodes codes={codes} onDone={() => setCodes([])} />
      </Paper>
    )

  return (
    <Stack gap="md">
      {s.required && !s.enabled && (
        <Alert color="orange" variant="light">
          {tr(
            'Als Plattform-Admin brauchst du einen Passkey oder die Authenticator-App. Bis eines davon eingerichtet ist, bleibt der Plattform-Bereich in der Verwaltung gesperrt.',
            'As a platform admin you need a passkey or the authenticator app. Until one is set up, the platform area in manage stays locked.',
          )}
        </Alert>
      )}
      <PasskeysCard s={s} showCodes={setCodes} />
      <AppCard s={s} showCodes={setCodes} />
      {s.enabled && <RecoveryCard s={s} showCodes={setCodes} />}
    </Stack>
  )
}
