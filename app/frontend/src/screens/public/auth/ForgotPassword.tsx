import { useState } from 'react'
import { TextInput, Button, Stack, Text, Title, ThemeIcon } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { AuthFrame } from './AuthFrame'

const schema = z.object({
  email: z.string().email('Invalid email'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPasswordScreen() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { email: '' },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await authApi.forgotPassword(values.email.trim().toLowerCase())
    } catch {
      // Same answer whether or not the address exists.
    } finally {
      setSent(true)
      setLoading(false)
    }
  }

  const back = (
    <Button
      variant="subtle"
      leftSection={<IconArrowLeft size={16} />}
      onClick={() => navigate('/login')}
    >
      Back to login
    </Button>
  )

  if (sent)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="xs">
          <ThemeIcon size={56} radius="xl" color="green" variant="light">
            <IconCheck size={28} />
          </ThemeIcon>
          <Title order={2}>Check your inbox</Title>
          <Text size="sm" c="dimmed" mb="md">
            If an account exists for {form.values.email}, a password reset link has been sent.
          </Text>
          {back}
        </Stack>
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <ThemeIcon size={48} radius="xl" color="yellow" variant="light" mb="md">
        <IconMail size={22} />
      </ThemeIcon>
      <Title order={2} mb={6}>
        Reset your password
      </Title>
      <Text size="sm" c="dimmed" mb={28}>
        Enter your email and we'll send you a reset link.
      </Text>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <TextInput label="Email" type="email" autoFocus {...form.getInputProps('email')} />
          <Button type="submit" fullWidth loading={loading}>
            Send reset link
          </Button>
          {back}
        </Stack>
      </form>
    </AuthFrame>
  )
}
