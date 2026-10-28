import { useState } from 'react'
import { PasswordInput, Button, Alert, Stack, Text, Title, ThemeIcon } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconKey } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { AuthFrame } from './AuthFrame'

const schema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

type FormValues = z.infer<typeof schema>

/** Opened from the reset mail: /reset-password#token=… */
export function ResetPasswordScreen() {
  const navigate = useNavigate()
  const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token') ?? ''
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { password: '', confirm: '' },
  })

  const handleReset = async (values: FormValues) => {
    setError('')
    setLoading(true)
    try {
      await authApi.resetPassword(token, values.password)
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired link.')
    } finally {
      setLoading(false)
    }
  }

  if (!token)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="md">
          <Text c="red" size="sm">
            This reset link is invalid or incomplete.
          </Text>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/forgot-password')}
          >
            Request a new link
          </Button>
        </Stack>
      </AuthFrame>
    )

  if (done)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="xs">
          <ThemeIcon size={56} radius="xl" color="green" variant="light">
            <IconCheck size={28} />
          </ThemeIcon>
          <Title order={2}>Password updated</Title>
          <Text size="sm" c="dimmed" mb="md">
            You can now sign in with your new password.
          </Text>
          <Button fullWidth onClick={() => navigate('/login')}>
            Sign in
          </Button>
        </Stack>
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <ThemeIcon size={48} radius="xl" color="yellow" variant="light" mb="md">
        <IconKey size={22} />
      </ThemeIcon>
      <Title order={2} mb={6}>
        Set a new password
      </Title>
      <Text size="sm" c="dimmed" mb={28}>
        Choose a strong password for your account.
      </Text>
      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}
      <form onSubmit={form.onSubmit(handleReset)}>
        <Stack gap="md">
          <PasswordInput label="New password" autoFocus {...form.getInputProps('password')} />
          <PasswordInput label="Confirm password" {...form.getInputProps('confirm')} />
          <Button type="submit" fullWidth loading={loading}>
            Set new password
          </Button>
        </Stack>
      </form>
    </AuthFrame>
  )
}
