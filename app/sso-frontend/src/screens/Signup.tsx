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

const DEFAULT_MANAGE_URL = import.meta.env.VITE_MANAGE_URL ?? 'https://manage.vollbuild.ch'

function passwordStrength(password: string): { value: number; label: string; color: string } {
  if (!password) return { value: 0, label: '', color: 'gray' }
  let score = 0
  if (password.length >= 12) score += 25
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 25
  if (/\d/.test(password)) score += 25
  if (/[^a-zA-Z0-9]/.test(password)) score += 25
  if (score < 50) return { value: score, label: 'Weak', color: 'red' }
  if (score < 75) return { value: score, label: 'Fair', color: 'yellow' }
  return { value: score, label: 'Strong', color: 'green' }
}

export function SignupScreen() {
  const { notify } = useSso()
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
      setError('All fields are required')
      return
    }
    setLoading(true)
    try {
      await authApi.signup(name, email.trim().toLowerCase(), password, keepSignedIn)
      notify('success', 'Account created', 'Welcome to Hubra.')
      window.location.assign(DEFAULT_MANAGE_URL)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Signup failed'
      setError(msg)
      notify('error', 'Signup failed', msg)
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
              <Text fz="md" fw={700}>Hubra</Text>
              <Text fz="xs" c="#8a6a00" ff="'JetBrains Mono', monospace" style={{ letterSpacing: '0.06em' }}>
                Makerspace · Schwyz
              </Text>
            </Box>
          </Group>

          <Title order={2} mb={6}>Create account</Title>
          <Text size="sm" c="dimmed" mb={28}>
            Sign up to request a space or join an existing one.
          </Text>

          {error && <Alert color="red" variant="light" mb="md">{error}</Alert>}

          <Stack gap="md">
            <TextInput
              label="Full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
              placeholder="Jane Doe"
            />

            <TextInput
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
              placeholder="jane@example.ch"
            />

            <Box>
              <PasswordInput
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSignup()}
                placeholder="At least 12 characters"
              />
              {password && (
                <Group gap="xs" mt={6}>
                  <Progress value={strength.value} color={strength.color} size="xs" style={{ flex: 1 }} />
                  <Text fz="xs" c="dimmed">{strength.label}</Text>
                </Group>
              )}
              <Text fz="xs" c="dimmed" mt={4}>
                Minimum 12 characters with a mix of letters, numbers, and symbols.
              </Text>
            </Box>

            <Checkbox
              label="Keep me signed in"
              checked={keepSignedIn}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setKeepSignedIn(e.currentTarget.checked)}
            />

            <Button size="sm" fullWidth onClick={handleSignup} loading={loading} mt={4}>
              {loading ? 'Creating account…' : 'Create account'}
            </Button>

            <Text size="sm" c="dimmed" ta="center">
              Already have an account?{' '}
              <Anchor size="sm" c="#8a6a00" onClick={(e) => { e.preventDefault(); navigate('/login') }}>
                Sign in
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
            v2.4 · Signup
          </Text>
          <blockquote style={{ margin: 0, fontSize: 'var(--mantine-font-size-lg)', lineHeight: 1.6, color: '#3a4048', maxWidth: 340 }}>
            "New here?{' '}
            <span className="hi">Request a space</span>{' '}
            and our team will get you set up — or{' '}
            <span className="hi">join an existing one</span>{' '}
            with an invite from your admin."
          </blockquote>
        </div>
      </Box>
    </div>
  )
}
