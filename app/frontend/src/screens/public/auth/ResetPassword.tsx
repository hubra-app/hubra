import { useState } from 'react'
import { PasswordInput, Button, Alert, Stack, Text, Title, ThemeIcon } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconKey } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { useT } from '@/locales/i18n'
import { AuthFrame } from './AuthFrame'

type FormValues = { password: string; confirm: string }

/** Opened from the reset mail: /reset-password#token=… */
export function ResetPasswordScreen() {
  const navigate = useNavigate()
  const { t } = useT()
  const schema = z
    .object({
      password: z.string().min(8, t('auth.passwordMin8', 'Mindestens 8 Zeichen.')),
      confirm: z.string(),
    })
    .refine((d) => d.password === d.confirm, {
      message: t('auth.passwordsDontMatch', 'Die Passwörter stimmen nicht überein.'),
      path: ['confirm'],
    })
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
      setError(err instanceof Error ? err.message : t('auth.linkExpired', 'Der Link ist ungültig oder abgelaufen.'))
    } finally {
      setLoading(false)
    }
  }

  if (!token)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="md">
          <Text c="red" size="sm">
            {t('auth.resetLinkInvalid', 'Dieser Link ist ungültig oder unvollständig.')}
          </Text>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/forgot-password')}
          >
            {t('auth.requestNewLink', 'Neuen Link anfordern')}
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
          <Title order={2}>{t('auth.passwordUpdated', 'Passwort geändert')}</Title>
          <Text size="sm" c="dimmed" mb="md">
            {t('auth.signInWithNew', 'Du kannst dich jetzt mit dem neuen Passwort anmelden.')}
          </Text>
          <Button fullWidth size="md" onClick={() => navigate('/login')}>
            {t('auth.signIn', 'Anmelden')}
          </Button>
        </Stack>
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <ThemeIcon size={48} radius="xl" color="acc" variant="light" mb="lg">
        <IconKey size={22} />
      </ThemeIcon>
      <Title order={1} fz={28} mb={6}>
        {t('auth.newPasswordTitle', 'Neues Passwort festlegen')}
      </Title>
      <Text size="md" c="dimmed" mb={32}>
        {t('auth.newPasswordSubtitle', 'Wähle ein sicheres Passwort für dein Konto.')}
      </Text>
      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}
      <form onSubmit={form.onSubmit(handleReset)}>
        <Stack gap="md">
          <PasswordInput
            label={t('auth.newPassword', 'Neues Passwort')}
            size="md"
            autoComplete="new-password"
            autoFocus {...form.getInputProps('password')} />
          <PasswordInput
            label={t('auth.confirmPassword', 'Passwort bestätigen')}
            size="md"
            autoComplete="new-password" {...form.getInputProps('confirm')} />
          <Button type="submit" size="md" fullWidth loading={loading}>
            {t('auth.saveNewPassword', 'Passwort speichern')}
          </Button>
        </Stack>
      </form>
    </AuthFrame>
  )
}
