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
import { useSso } from '@/context/SsoContext'
import { getRememberedEmail } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { AuthFrame } from '@/components/AuthFrame'
import { tr, useLang } from '@/lang'

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

  const form = useForm<FormValues>({
    validate: (values) => zodResolver(makeSchema())(values),
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
      await authApi.login(
        values.email.trim().toLowerCase(),
        values.password,
        values.keepSignedIn,
      )
      continueSignedIn()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : tr('Anmeldung fehlgeschlagen', 'Login failed')
      setError(msg)
      notify('error', tr('Anmelden', 'Sign in'), msg)
    } finally {
      setLoading(false)
    }
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
        <Button variant="default" size="md" fullWidth onClick={() => navigate(`/signup${window.location.search}`)}>
          {tr('Konto erstellen', 'Create account')}
        </Button>
      </Stack>
    </AuthFrame>
  )
}
