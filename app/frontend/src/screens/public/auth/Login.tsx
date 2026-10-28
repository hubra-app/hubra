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
import { AuthFrame } from './AuthFrame'

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
  keepSignedIn: z.boolean(),
})

type FormValues = z.infer<typeof schema>

/** Sign-in for single-club installs; multi-club installs use the SSO portal. */
export function LoginScreen() {
  const { homePath } = useInstance()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
      if (res.requiresTenantSelection || res.noTenant) {
        setError('This account is not a member of this club')
        setLoading(false)
        return
      }
      const returnTo = safeReturnPath(new URLSearchParams(window.location.search).get('redirect'))
      // A full page load, so the app starts over with the new session.
      window.location.assign(returnTo ?? homePath ?? '/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
      setLoading(false)
    }
  }

  return (
    <AuthFrame>
      <Title order={2} mb={6}>
        Welcome back
      </Title>
      <Text size="sm" c="dimmed" mb={28}>
        Sign in to your account
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <form onSubmit={form.onSubmit(handleLogin)}>
        <Stack gap="md">
          <TextInput label="Email" type="email" autoFocus {...form.getInputProps('email')} />

          <Box>
            <Group justify="space-between" mb={6}>
              <Text component="label" size="sm" fw={600} c="dimmed">
                Password
              </Text>
              <Anchor
                size="sm"
                c="#8a6a00"
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

      <Divider label="Not a member yet?" labelPosition="center" c="dimmed" my="lg" />
      <Button variant="default" size="sm" fullWidth onClick={() => navigate('/apply')}>
        Apply for membership
      </Button>
    </AuthFrame>
  )
}
