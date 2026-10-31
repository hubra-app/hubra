import { useState } from 'react'
import {
  TextInput,
  PasswordInput,
  Button,
  Checkbox,
  Alert,
  Stack,
  Group,
  Text,
  Title,
  Anchor,
  Divider,
  Box,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { getRememberedEmail } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { AuthFrame } from '@/components/AuthFrame'
import { tr, useLang } from '@/lang'
import { getPasskey, passkeyCancelled, passkeysSupported } from '@/webauthn'

// Built per render so the messages follow the chosen language.
const makeSchema = () =>
  z.object({
    email: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')),
    password: z.string().min(1, tr('Bitte gib dein Passwort ein', 'Password is required')),
    keepSignedIn: z.boolean(),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

export function LoginScreen() {
  const { notify, continueSignedIn } = useSso()
  const { tr } = useLang()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // Set when the password was right and two-factor is on.
  const [mfaToken, setMfaToken] = useState('')
  const [code, setCode] = useState('')

  const form = useForm<FormValues>({
    validate: (values) => zod4Resolver(makeSchema())(values),
    initialValues: {
      email: getRememberedEmail(),
      password: '',
      keepSignedIn: true,
    },
  })

  const handleLogin = async (values: FormValues) => {
    setError('')
    setLoading(true)
    try {
      // Everyone lands on the club picker (/clubs), unless a ?redirect=
      // deep link says where to go.
      const res = await authApi.login(
        values.email.trim().toLowerCase(),
        values.password,
        values.keepSignedIn,
      )
      if (res.mfaRequired && res.mfaToken) {
        setMfaToken(res.mfaToken)
        setCode('')
        return
      }
      continueSignedIn()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : tr('Anmeldung fehlgeschlagen', 'Login failed')
      setError(msg)
      notify('error', tr('Anmelden', 'Sign in'), msg)
    } finally {
      setLoading(false)
    }
  }

  /** Sign in with a passkey: on its own, or as the step after the password. */
  const handlePasskey = async () => {
    setError('')
    setLoading(true)
    try {
      const start = await authApi.passkeyLoginOptions(mfaToken || undefined)
      const credential = await getPasskey(start.options)
      await authApi.passkeyLogin(start.state, credential, {
        mfaToken: mfaToken || undefined,
        keepSignedIn: form.values.keepSignedIn,
      })
      continueSignedIn()
    } catch (err: unknown) {
      if (passkeyCancelled(err)) return
      const e2 = err as { code?: string; message?: string }
      if (e2.code === 'MFA_EXPIRED') setMfaToken('')
      setError(
        e2.code === 'PASSKEY_INVALID'
          ? tr('Dieser Passkey gehört zu keinem Konto hier.', 'This passkey belongs to no account here.')
          : e2.message || tr('Anmeldung fehlgeschlagen', 'Login failed'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleCode = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.loginMfa(mfaToken, code.trim())
      continueSignedIn()
    } catch (err: unknown) {
      const e2 = err as { code?: string; message?: string }
      if (e2.code === 'MFA_EXPIRED' || e2.code === 'ACCOUNT_LOCKED') setMfaToken('')
      setError(e2.message || tr('Anmeldung fehlgeschlagen', 'Login failed'))
    } finally {
      setLoading(false)
    }
  }

  if (mfaToken) {
    return (
      <AuthFrame>
        <Title order={1} fz={30} mb={6}>
          {tr('Bestätigungscode', 'Verification code')}
        </Title>
        <Text c="dimmed" mb={28}>
          {tr(
            'Gib den 6-stelligen Code aus deiner Authenticator-App ein, oder nimm deinen Passkey. Ohne beides geht auch ein Wiederherstellungscode.',
            'Enter the 6-digit code from your authenticator app, or use your passkey. Without either, a recovery code works too.',
          )}
        </Text>

        {error && (
          <Alert color="red" variant="light" mb="md">
            {error}
          </Alert>
        )}

        <form onSubmit={handleCode}>
          <Stack gap="md">
            <TextInput
              label={tr('Code', 'Code')}
              autoComplete="one-time-code"
              autoFocus
              size="md"
              value={code}
              onChange={(e) => setCode(e.currentTarget.value)}
            />
            <Button type="submit" size="md" fullWidth loading={loading} disabled={!code.trim()}>
              {tr('Bestätigen', 'Verify')}
            </Button>
            {passkeysSupported() && (
              <Button variant="default" size="md" fullWidth onClick={handlePasskey} disabled={loading}>
                {tr('Passkey verwenden', 'Use a passkey')}
              </Button>
            )}
            <Anchor
              size="sm"
              ta="center"
              onClick={(e) => {
                e.preventDefault()
                setMfaToken('')
                setError('')
              }}
            >
              {tr('Zurück zur Anmeldung', 'Back to sign in')}
            </Anchor>
          </Stack>
        </form>
      </AuthFrame>
    )
  }

  return (
    <AuthFrame>
      <Title order={1} fz={30} mb={6}>
        {tr('Willkommen zurück', 'Welcome back')}
      </Title>
      <Text c="dimmed" mb={28}>
        {tr('Melde dich mit deinem Hubra-Konto an.', 'Sign in to your Hubra account.')}
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <form onSubmit={form.onSubmit(handleLogin)}>
        <Stack gap="md">
          <TextInput
            label={tr('E-Mail', 'Email')}
            type="email"
            autoComplete="email"
            size="md"
            {...form.getInputProps('email')}
          />

          <Box>
            <Group justify="space-between" mb={4}>
              <Text component="label" htmlFor="login-password" size="sm" fw={600}>
                {tr('Passwort', 'Password')}
              </Text>
              <Anchor
                size="sm"
                fw={600}
                onClick={(e) => {
                  e.preventDefault()
                  navigate('/forgot-password')
                }}
              >
                {tr('Passwort vergessen?', 'Forgot password?')}
              </Anchor>
            </Group>
            <PasswordInput
              id="login-password"
              autoComplete="current-password"
              size="md"
              {...form.getInputProps('password')}
            />
          </Box>

          <Checkbox
            label={tr('Angemeldet bleiben', 'Keep me signed in')}
            {...form.getInputProps('keepSignedIn', { type: 'checkbox' })}
          />

          <Button type="submit" size="md" fullWidth loading={loading} mt={4}>
            {tr('Anmelden', 'Sign in')}
          </Button>
        </Stack>
      </form>

      <Divider label={tr('oder', 'or')} labelPosition="center" my="lg" />

      <Stack gap="xs">
        {passkeysSupported() && (
          <Button variant="default" size="md" fullWidth onClick={handlePasskey} disabled={loading}>
            {tr('Mit Passkey anmelden', 'Sign in with a passkey')}
          </Button>
        )}
        <Button variant="default" size="md" fullWidth onClick={() => navigate(`/signup${window.location.search}`)}>
          {tr('Konto erstellen', 'Create account')}
        </Button>
      </Stack>
    </AuthFrame>
  )
}
