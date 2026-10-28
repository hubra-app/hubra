import { useState } from 'react'
import { TextInput, Button, Stack, Text, Title, ThemeIcon } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { useT } from '@/locales/i18n'
import { AuthFrame } from './AuthFrame'

type FormValues = { email: string }

export function ForgotPasswordScreen() {
  const navigate = useNavigate()
  const { t } = useT()
  const schema = z.object({
    email: z.string().email(t('auth.invalidEmail', 'Bitte gib eine gültige E-Mail-Adresse ein.')),
  })
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
      {t('auth.backToLogin', 'Zurück zur Anmeldung')}
    </Button>
  )

  if (sent)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="xs">
          <ThemeIcon size={56} radius="xl" color="green" variant="light">
            <IconCheck size={28} />
          </ThemeIcon>
          <Title order={2}>{t('auth.checkInbox', 'Schau in dein Postfach')}</Title>
          <Text size="sm" c="dimmed" mb="md">
            {t(
              'auth.resetSent',
              'Falls es ein Konto für {{email}} gibt, haben wir dir einen Link zum Zurücksetzen geschickt.',
              { email: form.values.email },
            )}
          </Text>
          {back}
        </Stack>
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <ThemeIcon size={48} radius="xl" color="acc" variant="light" mb="lg">
        <IconMail size={22} />
      </ThemeIcon>
      <Title order={1} fz={28} mb={6}>
        {t('auth.resetTitle', 'Passwort zurücksetzen')}
      </Title>
      <Text size="md" c="dimmed" mb={32}>
        {t('auth.resetSubtitle', 'Gib deine E-Mail-Adresse ein. Wir schicken dir einen Link.')}
      </Text>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <TextInput
            label={t('auth.email', 'E-Mail')}
            type="email"
            size="md"
            autoComplete="email"
            autoFocus {...form.getInputProps('email')} />
          <Button type="submit" size="md" fullWidth loading={loading}>
            {t('auth.sendResetLink', 'Link senden')}
          </Button>
          {back}
        </Stack>
      </form>
    </AuthFrame>
  )
}
