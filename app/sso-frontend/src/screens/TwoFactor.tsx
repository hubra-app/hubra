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

type Step = 'idle' | 'start' | 'scan' | 'codes' | 'disable' | 'renew'

export function TwoFactorTab() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['mfa'], queryFn: authApi.getMfa })
  const [step, setStep] = useState<Step>('idle')
  const [setup, setSetup] = useState<authApi.TotpSetup | null>(null)
  const [codes, setCodes] = useState<string[]>([])
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  const go = (next: Step) => {
    setError('')
    setStep(next)
  }
  const saved = (s: authApi.MfaStatus) => queryClient.setQueryData(['mfa'], s)

  const start = useMutation({
    mutationFn: authApi.startTotpSetup,
    onSuccess: (s) => {
      setSetup(s)
      setCode('')
      go('scan')
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  const enable = useMutation({
    mutationFn: () => authApi.enableTotp(code.trim()),
    onSuccess: ({ recoveryCodes, ...s }) => {
      saved(s)
      setCodes(recoveryCodes)
      setSetup(null)
      go('codes')
      notify('success', tr('Zwei-Faktor-Anmeldung ist an', 'Two-factor sign-in is on'))
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  const disable = useMutation({
    mutationFn: authApi.disableTotp,
    onSuccess: (s) => {
      saved(s)
      go('idle')
      notify('success', tr('Zwei-Faktor-Anmeldung ist aus', 'Two-factor sign-in is off'))
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })
  const renew = useMutation({
    mutationFn: authApi.renewRecoveryCodes,
    onSuccess: ({ recoveryCodes, ...s }) => {
      saved(s)
      setCodes(recoveryCodes)
      go('codes')
    },
    onError: (err) => setError(errorText(err, tr('Fehlgeschlagen', 'Failed'))),
  })

  if (status.isError) return <LoadFailed onRetry={() => status.refetch()} />
  if (!status.data) return <Loader size="sm" />
  const s = status.data

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
          <Badge color={s.enabled ? 'green' : 'gray'} variant="light" style={{ flexShrink: 0 }}>
            {s.enabled ? tr('An', 'On') : tr('Aus', 'Off')}
          </Badge>
        </Group>

        {s.required && !s.enabled && step === 'idle' && (
          <Alert color="orange" variant="light">
            {tr(
              'Als Plattform-Admin brauchst du die Zwei-Faktor-Anmeldung. Bis sie an ist, bleibt der Plattform-Bereich in der Verwaltung gesperrt.',
              'As a platform admin you need two-factor sign-in. Until it is on, the platform area in manage stays locked.',
            )}
          </Alert>
        )}

        {step === 'codes' && <RecoveryCodes codes={codes} onDone={() => go('idle')} />}

        {step === 'idle' && !s.enabled && (
          <Group justify="flex-end">
            <Button onClick={() => go('start')}>{tr('Einrichten', 'Set up')}</Button>
          </Group>
        )}

        {step === 'idle' && s.enabled && (
          <>
            <Text size="sm">
              {tr(
                `Noch ${s.recoveryCodesLeft} von 10 Wiederherstellungscodes übrig.`,
                `${s.recoveryCodesLeft} of 10 recovery codes left.`,
              )}
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => go('renew')}>
                {tr('Neue Wiederherstellungscodes', 'New recovery codes')}
              </Button>
              <Button variant="light" color="red" onClick={() => go('disable')}>
                {tr('Ausschalten', 'Turn off')}
              </Button>
            </Group>
          </>
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

        {step === 'renew' && (
          <PasswordStep
            label={tr('Neue Codes erstellen', 'Create new codes')}
            pending={renew.isPending}
            error={error}
            onConfirm={(pw) => renew.mutate(pw)}
            onCancel={() => go('idle')}
          />
        )}
      </Stack>
    </Paper>
  )
}
