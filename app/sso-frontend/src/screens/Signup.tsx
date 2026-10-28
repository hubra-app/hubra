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
  Center,
  Progress,
} from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import * as authApi from '@/api/auth'
import { tr, useLang } from '@/lang'
import { LangSwitch } from '@/components/LangSwitch'

function passwordStrength(password: string): { value: number; label: string; color: string } {
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
  useLang()
  const { notify, continueSignedIn } = useSso()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keepSignedIn, setKeepSignedIn] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const strength = passwordStrength(password)

  const handleSignup = async () => {
    setError('')
    if (!name || !email || !password) {
      setError(tr('Bitte fülle alle Felder aus', 'All fields are required'))
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

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex' }}>
      <Center flex={1} p={32}>
        <Box style={{ width: '100%', maxWidth: 380 }}>
          <Group gap={10} mb={32}>
            <div className="logo-mark" />
            <Box>
              <Text fz={20} className="wordmark">hubra</Text>
              <Text fz="xs" c="#6131c4" ff="'JetBrains Mono', monospace" style={{ letterSpacing: '0.06em' }}>
                {tr('Vereinsverwaltung', 'Club management')}
              </Text>
            </Box>
            <LangSwitch />
          </Group>

          <Title order={2} mb={6}>{tr('Konto erstellen', 'Create account')}</Title>
          <Text size="sm" c="dimmed" mb={28}>
            {tr(
              'Mit einem Konto gründest du einen Verein oder trittst einem bestehenden bei.',
              'Sign up to start a club or join an existing one.',
            )}
          </Text>

          {error && <Alert color="red" variant="light" mb="md">{error}</Alert>}

          <Stack gap="md">
            <TextInput
              label={tr('Vor- und Nachname', 'Full name')}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
              placeholder={tr('Anna Muster', 'Jane Doe')}
            />

            <TextInput
              label={tr('E-Mail', 'Email')}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
              placeholder={tr('anna@beispiel.ch', 'jane@example.ch')}
            />

            <Box>
              <PasswordInput
                label={tr('Passwort', 'Password')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
                placeholder={tr('Mindestens 12 Zeichen', 'At least 12 characters')}
              />
              {password && (
                <Group gap="xs" mt={6}>
                  <Progress value={strength.value} color={strength.color} size="xs" style={{ flex: 1 }} />
                  <Text fz="xs" c="dimmed">{strength.label}</Text>
                </Group>
              )}
              <Text fz="xs" c="dimmed" mt={4}>
                {tr(
                  'Mindestens 12 Zeichen, gemischt aus Buchstaben, Ziffern und Sonderzeichen.',
                  'Minimum 12 characters with a mix of letters, numbers, and symbols.',
                )}
              </Text>
            </Box>

            <Checkbox
              label={tr('Angemeldet bleiben', 'Keep me signed in')}
              checked={keepSignedIn}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeepSignedIn(e.currentTarget.checked)}
            />

            <Button size="sm" fullWidth onClick={handleSignup} loading={loading} mt={4}>
              {loading ? tr('Konto wird erstellt …', 'Creating account…') : tr('Konto erstellen', 'Create account')}
            </Button>

            <Text size="sm" c="dimmed" ta="center">
              {tr('Schon ein Konto?', 'Already have an account?')}{' '}
              <Anchor size="sm" c="#6131c4" onClick={(e) => { e.preventDefault(); navigate('/login') }}>
                {tr('Anmelden', 'Sign in')}
              </Anchor>
            </Text>
          </Stack>
        </Box>
      </Center>

      <Box
        className="mantine-visible-from-sm"
        style={{ width: '46%', position: 'relative', display: 'flex', alignItems: 'stretch' }}
      >
        <div className="blueprint-plate" style={{ flex: 1, margin: 24 }}>
          <div className="blueprint-label">SCHNITT Nr. 002 · MASSSTAB 1:1</div>
          <Text fz="xs" c="dimmed" ff="'JetBrains Mono', monospace" mb={20} style={{ alignSelf: 'flex-end' }}>
            v2.4 · Konto
          </Text>
          <blockquote style={{ margin: 0, fontSize: 'var(--mantine-font-size-lg)', lineHeight: 1.6, color: '#2e2940', maxWidth: 340 }}>
            {tr('«Neu hier? ', '"New here? ')}
            <span className="hi">{tr('Gründe deinen Verein', 'Start your club')}</span>
            {tr(' oder ', ' or ')}
            <span className="hi">{tr('tritt einem bestehenden bei', 'join an existing one')}</span>
            {tr('.»', '."')}
          </blockquote>
        </div>
      </Box>
    </div>
  )
}
