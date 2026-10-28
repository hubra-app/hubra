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
  Paper,
  Box,
  Center,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconShield } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useAuth, useToast } from '@/context/AppContext'
import { getRememberedEmail } from '@vollbuild/api-client'
import * as authApi from '@/api/auth'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'

export function LoginScreen() {
  const { t } = useT()
  const { setPhase, setCurrentUser } = useAuth()
  const { notify } = useToast()
  const navigate = useNavigate()
  const [email, setEmail] = useState(getRememberedEmail())
  const [password, setPassword] = useState('')
  const [keepSignedIn, setKeepSignedIn] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async () => {
    setError('')
    setLoading(true)
    try {
      const { member, mustChangePassword } = await authApi.login(
        email.trim().toLowerCase(),
        password,
        keepSignedIn,
      )
      setCurrentUser({
        ...member,
        mustChangePassword: mustChangePassword ?? false,
      })
      setPhase('app')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
      notify('error', t('auth.login'), msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex' }}>
      {/* Left: Auth form */}
      <Center flex={1} p={32}>
        <Box style={{ width: '100%', maxWidth: 380 }}>
          {/* Language switcher */}
          <Group justify="flex-end" mb="md">
            <LanguageSwitcher />
          </Group>

          {/* Brand */}
          <Group gap={10} mb={32}>
            <div className="logo-mark" />
            <Box>
              <Text fz="md" fw={700}>
                VollBuild
              </Text>
              <Text
                fz="xs"
                c="#8a6a00"
                ff="'JetBrains Mono', monospace"
                style={{ letterSpacing: '0.06em' }}
              >
                Makerspace · Schwyz
              </Text>
            </Box>
          </Group>

          <Title order={2} mb={6}>
            {t('auth.welcomeBack')}
          </Title>
          <Text size="sm" c="dimmed" mb={28}>
            {t('auth.loginAdmin')}
          </Text>

          {error && (
            <Alert color="red" variant="light" mb="md">
              {error}
            </Alert>
          )}

          <Stack gap="md">
            <TextInput
              label={t('common.email')}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />

            <Box>
              <Group justify="space-between" mb={6}>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('common.password')}
                </Text>
                <Anchor
                  size="sm"
                  c="#8a6a00"
                  onClick={(e) => {
                    e.preventDefault()
                    navigate('/forgot-password')
                  }}
                >
                  {t('auth.forgot.link')}
                </Anchor>
              </Group>
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              />
            </Box>

            <Checkbox
              label={t('auth.keepSignedIn')}
              checked={keepSignedIn}
              onChange={(e) => setKeepSignedIn(e.currentTarget.checked)}
            />

            <Button size="sm" fullWidth onClick={handleLogin} loading={loading} mt={4}>
              {loading ? t('auth.signingIn') : t('auth.login')}
            </Button>

            <Divider label={t('common.or')} labelPosition="center" c="dimmed" />

            <Button
              variant="default"
              size="sm"
              fullWidth
              leftSection={<IconShield size={16} color="#2596be" />}
              onClick={() => setPhase('app')}
            >
              {t('auth.continueWithSso')}
            </Button>
          </Stack>

          <Text size="sm" c="dimmed" ta="center" mt={20}>
            {t('auth.wantToJoin')}{' '}
            <Anchor href="/apply" c="#8a6a00" fw={600}>
              {t('auth.applyForMembership')} →
            </Anchor>
          </Text>
        </Box>
      </Center>

      {/* Right: Blueprint plate — hidden on mobile */}
      <Box
        className="mantine-visible-from-sm"
        style={{
          width: '46%',
          position: 'relative',
          display: 'flex',
          alignItems: 'stretch',
        }}
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
            v2.4 · Spaces
          </Text>

          <blockquote
            style={{
              margin: 0,
              fontSize: 'var(--mantine-font-size-lg)',
              lineHeight: 1.6,
              color: '#3a4048',
              maxWidth: 340,
            }}
          >
            "The space where we manage our <span className="hi">members, dues, tools</span> and{' '}
            <span className="hi">mailing list</span> — all in one place."
          </blockquote>

          <Group gap={12} mt={32} wrap="wrap">
            {[
              { label: 'Members', value: '342' },
              { label: 'Groups', value: '7' },
              { label: 'Uptime', value: '98%' },
            ].map((chip) => (
              <Paper
                key={chip.label}
                withBorder
                radius="md"
                p="sm"
                style={{ background: 'rgba(255,255,255,.7)' }}
              >
                <Text className="num" fz="lg" fw={700}>
                  {chip.value}
                </Text>
                <Text fz="xs" c="dimmed">
                  {chip.label}
                </Text>
              </Paper>
            ))}
          </Group>
        </div>
      </Box>
    </div>
  )
}
