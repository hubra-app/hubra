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
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { getRememberedEmail } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { safeReturnPath, useInstance } from '@/context/InstanceContext'
import { useT } from '@/locales/i18n'
import { AuthFrame } from './AuthFrame'

const makeSchema = (t: (k: string, d: string) => string) =>
  z.object({
    email: z.string().email(t('auth.invalidEmail', 'Bitte gib eine gültige E-Mail-Adresse ein.')),
    password: z.string().min(1, t('auth.passwordRequired', 'Bitte gib dein Passwort ein.')),
    keepSignedIn: z.boolean(),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

/** Sign-in for single-club installs; multi-club installs use the SSO portal. */
export function LoginScreen() {
  const { homePath } = useInstance()
  const navigate = useNavigate()
  const { t } = useT()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const form = useForm<FormValues>({
    validate: zodResolver(makeSchema(t)),
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
      const res = await authApi.login(
        values.email.trim().toLowerCase(),
        values.password,
        values.keepSignedIn,
      )
      if (res.requiresTenantSelection || res.noTenant) {
        setError(t('auth.notMember', 'Dieses Konto ist kein Mitglied dieses Vereins.'))
        setLoading(false)
        return
      }
      const returnTo = safeReturnPath(new URLSearchParams(window.location.search).get('redirect'))
      // A full page load, so the app starts over with the new session.
      window.location.assign(returnTo ?? homePath ?? '/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('auth.loginFailed', 'Anmeldung fehlgeschlagen.'))
      setLoading(false)
    }
  }

  return (
    <AuthFrame>
      <Title order={1} fz={28} mb={6}>
        {t('auth.welcomeBack', 'Willkommen zurück')}
      </Title>
      <Text size="md" c="dimmed" mb={32}>
        {t('auth.signInSubtitle', 'Melde dich mit deinem Konto an.')}
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <form onSubmit={form.onSubmit(handleLogin)}>
        <Stack gap="md">
          <TextInput
            label={t('auth.email', 'E-Mail')}
            type="email"
            size="md"
            autoComplete="email"
            autoFocus {...form.getInputProps('email')} />

          <Box>
            <Group justify="space-between" mb={6}>
              <Text component="label" htmlFor="login-password" size="sm" fw={600}>
                {t('auth.password', 'Passwort')}
              </Text>
              <Anchor
                size="sm"
                fw={600}
                href="/forgot-password"
                onClick={(e) => {
                  e.preventDefault()
                  navigate('/forgot-password')
                }}
              >
                {t('auth.forgotPassword', 'Passwort vergessen?')}
              </Anchor>
            </Group>
            <PasswordInput
              id="login-password"
              size="md"
              autoComplete="current-password"
              {...form.getInputProps('password')}
            />
          </Box>

          <Checkbox
            label={t('auth.keepSignedIn', 'Angemeldet bleiben')}
            {...form.getInputProps('keepSignedIn', { type: 'checkbox' })}
          />

          <Button type="submit" size="md" fullWidth loading={loading} mt={4}>
            {t('auth.signIn', 'Anmelden')}
          </Button>
        </Stack>
      </form>

      <Divider
        label={t('auth.notMemberYet', 'Noch kein Mitglied?')}
        labelPosition="center"
        my="xl"
      />
      <Button variant="default" size="md" fullWidth onClick={() => navigate('/apply')}>
        {t('auth.applyForMembership', 'Mitgliedschaft beantragen')}
      </Button>
    </AuthFrame>
  )
}
