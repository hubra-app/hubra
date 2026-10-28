import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { TextInput, PasswordInput, Button, Paper, Stack, Text, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { notifications } from '@mantine/notifications'
import { login } from '@/api/auth'
import { useAdmin } from '@/context/AdminContext'

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
})

type FormValues = z.infer<typeof schema>

export function LoginScreen() {
  const navigate = useNavigate()
  const { authStatus } = useAdmin()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { email: '', password: '' },
  })

  if (authStatus === 'authed') return <Navigate to="/tenants" replace />

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    setError('')
    try {
      await login(values.email, values.password)
      notifications.show({
        title: 'Welcome',
        message: 'Login successful',
        color: 'green',
      })
      navigate('/tenants')
      window.location.reload()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#eef3f0',
        padding: 16,
      }}
    >
      <Paper shadow="lg" radius="lg" p={40} maw={420} style={{ width: '100%' }}>
        <Stack gap={20} align="center" mb={24}>
          <div className="logo-mark" style={{ width: 40, height: 40 }} />
          <div>
            <Title order={2} ta="center">
              Admin Portal
            </Title>
            <Text size="sm" c="dimmed" ta="center">
              Club Operations Suite
            </Text>
          </div>
        </Stack>

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack gap={16}>
            <TextInput
              label="Email"
              type="email"
              required
              {...form.getInputProps('email')}
              placeholder="admin@vollbuild.ch"
            />
            <PasswordInput
              label="Password"
              required
              {...form.getInputProps('password')}
            />
            {error && (
              <Text size="sm" c="red" fw={500}>
                {error}
              </Text>
            )}
            <Button type="submit" loading={loading} fullWidth size="md">
              Sign In
            </Button>
          </Stack>
        </form>
      </Paper>
    </div>
  )
}
