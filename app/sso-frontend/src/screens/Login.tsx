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
  Center,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { getRememberedEmail } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { tr, useLang } from '@/lang'
import { LangSwitch } from '@/components/LangSwitch'

const makeSchema = () =>
  z.object({
    email: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')),
    password: z.string().min(1, tr('Bitte gib dein Passwort ein', 'Password is required')),
    keepSignedIn: z.boolean(),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

export function LoginScreen() {
  useLang()
  const { notify, continueSignedIn } = useSso()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const form = useForm<FormValues>({
    validate: zodResolver(makeSchema()),
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
      const msg = err instanceof Error ? err.message : tr('Anmelden fehlgeschlagen', 'Login failed')
      setError(msg)
      notify('error', tr('Anmelden', 'Sign in'), msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex' }}>
      <Center flex={1} p={32}>
        <Box style={{ width: '100%', maxWidth: 380 }}>
          <Group gap={10} mb={32}>
            <div className="logo-mark" />
            <Box>
              <Text fz={20} className="wordmark">
                hubra
              </Text>
              <Text
                fz="xs"
                c="#6131c4"
                ff="'JetBrains Mono', monospace"
                style={{ letterSpacing: '0.06em' }}
              >
                {tr('Vereinsverwaltung', 'Club management')}
              </Text>
            </Box>
            <LangSwitch />
          </Group>

          <Title order={2} mb={6}>
            {tr('Willkommen zurück', 'Welcome back')}
          </Title>
          <Text size="sm" c="dimmed" mb={28}>
            {tr('Melde dich mit deinem Hubra-Konto an', 'Sign in to your Hubra account')}
          </Text>

          {error && (
            <Alert color="red" variant="light" mb="md">
              {error}
            </Alert>
          )}

          <Stack gap="md">
            <form onSubmit={form.onSubmit(handleLogin)}>
              <Stack gap="md">
                <TextInput label={tr('E-Mail', 'Email')} type="email" {...form.getInputProps('email')} />

                <Box>
                  <Group justify="space-between" mb={6}>
                    <Text component="label" size="sm" fw={600} c="dimmed">
                      {tr('Passwort', 'Password')}
                    </Text>
                    <Anchor
                      size="sm"
                      c="#6131c4"
                      onClick={(e) => {
                        e.preventDefault()
                        navigate('/forgot-password')
                      }}
                    >
                      {tr('Passwort vergessen?', 'Forgot password?')}
                    </Anchor>
                  </Group>
                  <PasswordInput {...form.getInputProps('password')} />
                </Box>

                <Checkbox
                  label={tr('Angemeldet bleiben', 'Keep me signed in')}
                  {...form.getInputProps('keepSignedIn', { type: 'checkbox' })}
                />

                <Button type="submit" size="sm" fullWidth loading={loading} mt={4}>
                  {loading ? tr('Anmelden …', 'Signing in…') : tr('Anmelden', 'Sign in')}
                </Button>
              </Stack>
            </form>

            <Divider label={tr('oder', 'or')} labelPosition="center" c="dimmed" />

            <Stack gap="sm">
              <Button variant="default" size="sm" fullWidth onClick={() => navigate('/signup')}>
                {tr('Konto erstellen', 'Create account')}
              </Button>
            </Stack>
          </Stack>
        </Box>
      </Center>

      <Box
        className="mantine-visible-from-sm"
        style={{ width: '46%', position: 'relative', display: 'flex', alignItems: 'stretch' }}
      >
        <div className="blueprint-plate" style={{ flex: 1, margin: 24 }}>
          <div className="blueprint-label">SCHNITT Nr. 001 · MASSSTAB 1:1</div>
          <Text
            fz="xs"
            c="dimmed"
            ff="'JetBrains Mono', monospace"
            mb={20}
            style={{ alignSelf: 'flex-end' }}
          >
            v2.4 · Anmeldung
          </Text>
          <blockquote
            style={{
              margin: 0,
              fontSize: 'var(--mantine-font-size-lg)',
              lineHeight: 1.6,
              color: '#2e2940',
              maxWidth: 340,
            }}
          >
            {tr('«Hier verwalten wir ', '"The place where we manage our ')}
            <span className="hi">{tr('Mitglieder, Beiträge, Anlässe', 'members, dues, events')}</span>
            {tr(' und ', ' and ')}
            <span className="hi">{tr('Finanzen', 'finances')}</span>
            {tr(', alles an einem Ort.»', ', all in one place."')}
          </blockquote>
        </div>
      </Box>
    </div>
  )
}
