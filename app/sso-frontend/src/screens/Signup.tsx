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
  Box,
  Progress,
} from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import * as authApi from '@/api/auth'
import { AuthFrame } from '@/components/AuthFrame'
import { useLang } from '@/lang'

function passwordStrength(password: string, tr: (de: string, en: string) => string) {
  if (!password) return { value: 0, label: '', color: 'gray' }
  let score = 0
  if (password.length >= 12) score += 25
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 25
  if (/\d/.test(password)) score += 25
  if (/[^a-zA-Z0-9]/.test(password)) score += 25
  if (score < 50) return { value: score, label: tr('Schwach', 'Weak'), color: 'red' }
  if (score < 75) return { value: score, label: tr('Mittel', 'Fair'), color: 'yellow' }
  return { value: score, label: tr('Stark', 'Strong'), color: 'green' }
}

export function SignupScreen() {
  const { notify, continueSignedIn } = useSso()
  const { tr } = useLang()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keepSignedIn, setKeepSignedIn] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const strength = passwordStrength(password, tr)

  const handleSignup = async () => {
    setError('')
    if (!name || !email || !password) {
      setError(tr('Bitte fülle alle Felder aus.', 'All fields are required.'))
      return
    }
    setLoading(true)
    try {
      await authApi.signup(name, email.trim().toLowerCase(), password, keepSignedIn)
      notify(
        'success',
        tr('Konto erstellt', 'Account created'),
        tr('Willkommen bei Hubra. Such jetzt deinen Verein.', 'Welcome to Hubra. Now find your club.'),
      )
      continueSignedIn()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : tr('Registrierung fehlgeschlagen', 'Signup failed')
      setError(msg)
      notify('error', tr('Registrierung fehlgeschlagen', 'Signup failed'), msg)
    } finally {
      setLoading(false)
    }
  }

  const onEnter = (e: React.KeyboardEvent) => e.key === 'Enter' && handleSignup()

  return (
    <AuthFrame>
      <Title order={1} fz={30} mb={6}>
        {tr('Konto erstellen', 'Create account')}
      </Title>
      <Text c="dimmed" mb={28}>
        {tr(
          'Ein Konto für alle deine Vereine. Danach trittst du einem Verein bei oder beantragst einen neuen.',
          'One account for all your clubs. Then join a club or request a new one.',
        )}
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <Stack gap="md">
        <TextInput
          label={tr('Vor- und Nachname', 'Full name')}
          autoComplete="name"
          size="md"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={onEnter}
          placeholder={tr('Anna Muster', 'Jane Doe')}
        />

        <TextInput
          label={tr('E-Mail', 'Email')}
          type="email"
          autoComplete="email"
          size="md"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={onEnter}
          placeholder="anna@example.ch"
        />

        <Box>
          <PasswordInput
            label={tr('Passwort', 'Password')}
            autoComplete="new-password"
            size="md"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={onEnter}
            placeholder={tr('Mindestens 12 Zeichen', 'At least 12 characters')}
          />
          {password && (
            <Group gap="xs" mt={8}>
              <Progress value={strength.value} color={strength.color} size="xs" style={{ flex: 1 }} />
              <Text fz="xs" c="dimmed">
                {strength.label}
              </Text>
            </Group>
          )}
          <Text fz="xs" c="dimmed" mt={6}>
            {tr(
              'Mindestens 12 Zeichen, gemischt aus Buchstaben, Zahlen und Sonderzeichen.',
              'At least 12 characters with a mix of letters, numbers and symbols.',
            )}
          </Text>
        </Box>

        <Checkbox
          label={tr('Angemeldet bleiben', 'Keep me signed in')}
          checked={keepSignedIn}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeepSignedIn(e.currentTarget.checked)}
        />

        <Button size="md" fullWidth onClick={handleSignup} loading={loading} mt={4}>
          {tr('Konto erstellen', 'Create account')}
        </Button>

        <Text size="sm" c="dimmed" ta="center">
          {tr('Du hast schon ein Konto?', 'Already have an account?')}{' '}
          <Anchor
            size="sm"
            fw={600}
            onClick={(e) => {
              e.preventDefault()
              navigate(`/login${window.location.search}`)
            }}
          >
            {tr('Anmelden', 'Sign in')}
          </Anchor>
        </Text>
      </Stack>
    </AuthFrame>
  )
}
