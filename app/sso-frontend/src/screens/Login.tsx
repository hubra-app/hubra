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
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconShield } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { getRememberedEmail } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { clubAppUrl, determineDefaultRedirect } from '@/context/SsoContext'

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
  keepSignedIn: z.boolean(),
})

type FormValues = z.infer<typeof schema>

export function LoginScreen() {
  const { notify, redirectTarget, isSuperadmin } = useSso()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tenants, setTenants] = useState<authApi.TenantChoice[] | null>(null)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
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
      if (res.requiresTenantSelection && res.tenants) {
        if (res.tenants.length === 1) {
          // Nothing to choose: open the one club straight away.
          await handleSelectTenant(res.tenants[0].tenant_slug)
          return
        }
        setTenants(res.tenants)
        return
      }
      if (res.noTenant) {
        const target = redirectTarget || determineDefaultRedirect(isSuperadmin)
        window.location.assign(target)
        return
      }
      const target =
        redirectTarget ||
        (res.tenant_slug ? clubAppUrl(res.tenant_slug) : determineDefaultRedirect(isSuperadmin))
      window.location.assign(target)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
      notify('error', 'Login', msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectTenant = async (slug: string) => {
    setLoading(true)
    setError('')
    try {
      await authApi.switchTenant(slug)
      window.location.assign(redirectTarget || clubAppUrl(slug))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Tenant switch failed'
      setError(msg)
      notify('error', 'Tenant Switch', msg)
    } finally {
      setLoading(false)
    }
  }

  if (tenants) {
    return (
      <div
        className="graph-bg"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 32,
        }}
      >
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
                Club management
              </Text>
            </Box>
          </Group>

          <Title order={2} mb={6}>
            Choose a club
          </Title>
          <Text size="sm" c="dimmed" mb={28}>
            Your account belongs to several clubs. Choose the one to open.
          </Text>

          {error && (
            <Alert color="red" variant="light" mb="md">
              {error}
            </Alert>
          )}

          <Stack gap="sm">
            {tenants.map((t) => (
              <Paper
                key={t.tenant_slug}
                withBorder
                radius="md"
                p="md"
                onClick={() => handleSelectTenant(t.tenant_slug)}
                style={{ cursor: 'pointer' }}
              >
                <Group justify="space-between">
                  <Box>
                    <Text fw={600}>{t.tenant_name}</Text>
                    <Text fz="xs" c="dimmed">
                      {t.tenant_slug}
                    </Text>
                  </Box>
                </Group>
              </Paper>
            ))}
          </Stack>

          <Button variant="subtle" fullWidth mt="md" onClick={() => setTenants(null)}>
            Back to login
          </Button>
        </Box>
      </div>
    )
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
                Club management
              </Text>
            </Box>
          </Group>

          <Title order={2} mb={6}>
            Welcome back
          </Title>
          <Text size="sm" c="dimmed" mb={28}>
            Sign in to your Hubra account
          </Text>

          {error && (
            <Alert color="red" variant="light" mb="md">
              {error}
            </Alert>
          )}

          <Stack gap="md">
            <form onSubmit={form.onSubmit(handleLogin)}>
              <Stack gap="md">
                <TextInput label="Email" type="email" {...form.getInputProps('email')} />

                <Box>
                  <Group justify="space-between" mb={6}>
                    <Text component="label" size="sm" fw={600} c="dimmed">
                      Password
                    </Text>
                    <Anchor
                      size="sm"
                      c="#6131c4"
                      onClick={(e) => {
                        e.preventDefault()
                        navigate('/forgot-password')
                      }}
                    >
                      Forgot password?
                    </Anchor>
                  </Group>
                  <PasswordInput {...form.getInputProps('password')} />
                </Box>

                <Checkbox
                  label="Keep me signed in"
                  {...form.getInputProps('keepSignedIn', { type: 'checkbox' })}
                />

                <Button type="submit" size="sm" fullWidth loading={loading} mt={4}>
                  {loading ? 'Signing in…' : 'Sign in'}
                </Button>
              </Stack>
            </form>

            <Divider label="or" labelPosition="center" c="dimmed" />

            <Stack gap="sm">
              <Button variant="default" size="sm" fullWidth onClick={() => navigate('/signup')}>
                Create account
              </Button>

              <Button
                variant="subtle"
                size="sm"
                fullWidth
                leftSection={<IconShield size={16} color="#2596be" />}
                onClick={() => {
                  window.location.assign(redirectTarget)
                }}
              >
                Continue as guest
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
            v2.4 · Spaces
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
