import { useState } from 'react'
import { TextInput, Button, Stack, Text, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { AuthFrame, AuthIcon } from '@/components/AuthFrame'
import { tr, useLang } from '@/lang'

const makeSchema = () =>
  z.object({
    email: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

export function ForgotPassword() {
  const navigate = useNavigate()
  const { tr } = useLang()
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const form = useForm<FormValues>({
    validate: (values) => zodResolver(makeSchema())(values),
    initialValues: { email: '' },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await authApi.forgotPassword(values.email.trim().toLowerCase())
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  const back = (
    <Button
      variant="subtle"
      fullWidth
      leftSection={<IconArrowLeft size={16} />}
      onClick={() => navigate('/login')}
    >
      {tr('Zurück zur Anmeldung', 'Back to sign in')}
    </Button>
  )

  if (sent)
    return (
      <AuthFrame>
        <AuthIcon tone="green">
          <IconCheck size={26} color="#1f9d57" />
        </AuthIcon>
        <Title order={1} fz={30} mb={8}>
          {tr('Schau in dein Postfach', 'Check your inbox')}
        </Title>
        <Text c="dimmed" mb={28} lh={1.6}>
          {tr(
            `Falls es ein Konto für ${form.values.email} gibt, haben wir dir einen Link zum Zurücksetzen geschickt.`,
            `If an account exists for ${form.values.email}, we have sent a reset link.`,
          )}
        </Text>
        {back}
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <AuthIcon>
        <IconMail size={24} color="#6131c4" />
      </AuthIcon>
      <Title order={1} fz={30} mb={6}>
        {tr('Passwort vergessen', 'Reset your password')}
      </Title>
      <Text c="dimmed" mb={28}>
        {tr(
          'Gib deine E-Mail-Adresse ein. Wir schicken dir einen Link für ein neues Passwort.',
          "Enter your email and we'll send you a reset link.",
        )}
      </Text>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <TextInput
            label={tr('E-Mail', 'Email')}
            type="email"
            autoComplete="email"
            size="md"
            autoFocus
            {...form.getInputProps('email')}
          />
          <Button type="submit" size="md" fullWidth loading={loading}>
            {tr('Link senden', 'Send reset link')}
          </Button>
          {back}
        </Stack>
      </form>
    </AuthFrame>
  )
}
