import { useState } from 'react'
import { PasswordInput, Button, Alert, Stack, Text, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconKey, IconLinkOff } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { AuthFrame, AuthIcon } from '@/components/AuthFrame'
import { tr, useLang } from '@/lang'

const makeSchema = () =>
  z
    .object({
      password: z
        .string()
        .min(12, tr('Das Passwort braucht mindestens 12 Zeichen', 'Password must be at least 12 characters')),
      confirm: z.string(),
    })
    .refine((d) => d.password === d.confirm, {
      message: tr('Die Passwörter stimmen nicht überein', 'Passwords do not match'),
      path: ['confirm'],
    })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

export function ResetPassword() {
  const navigate = useNavigate()
  const { tr } = useLang()
  const hashParams = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : '',
  )
  const token = hashParams.get('token') ?? ''
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const form = useForm<FormValues>({
    validate: (values) => zod4Resolver(makeSchema())(values),
    initialValues: { password: '', confirm: '' },
  })

  const handleReset = async (values: FormValues) => {
    setError('')
    setLoading(true)
    try {
      await authApi.resetPassword(token, values.password)
      setDone(true)
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : tr('Der Link ist ungültig oder abgelaufen.', 'Invalid or expired token.'),
      )
    } finally {
      setLoading(false)
    }
  }

  if (!token)
    return (
      <AuthFrame>
        <AuthIcon tone="red">
          <IconLinkOff size={24} color="#b91c1c" />
        </AuthIcon>
        <Title order={1} fz={30} mb={8}>
          {tr('Link ungültig', 'Link not valid')}
        </Title>
        <Text c="dimmed" mb={28}>
          {tr(
            'Dieser Link ist unvollständig oder abgelaufen. Fordere einfach einen neuen an.',
            'This link is incomplete or has expired. Just request a new one.',
          )}
        </Text>
        <Button size="md" fullWidth onClick={() => navigate('/forgot-password')}>
          {tr('Neuen Link anfordern', 'Request a new link')}
        </Button>
      </AuthFrame>
    )

  if (done)
    return (
      <AuthFrame>
        <AuthIcon tone="green">
          <IconCheck size={26} color="#1f9d57" />
        </AuthIcon>
        <Title order={1} fz={30} mb={8}>
          {tr('Passwort geändert', 'Password updated')}
        </Title>
        <Text c="dimmed" mb={28}>
          {tr('Du kannst dich jetzt mit dem neuen Passwort anmelden.', 'You can now sign in with your new password.')}
        </Text>
        <Button size="md" fullWidth onClick={() => navigate('/login')}>
          {tr('Zur Anmeldung', 'Go to sign in')}
        </Button>
      </AuthFrame>
    )

  return (
    <AuthFrame>
      <AuthIcon>
        <IconKey size={24} color="#6131c4" />
      </AuthIcon>
      <Title order={1} fz={30} mb={6}>
        {tr('Neues Passwort setzen', 'Set a new password')}
      </Title>
      <Text c="dimmed" mb={28}>
        {tr('Wähle ein sicheres Passwort für dein Konto.', 'Choose a strong password for your account.')}
      </Text>
      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}
      <form onSubmit={form.onSubmit(handleReset)}>
        <Stack gap="md">
          <PasswordInput
            label={tr('Neues Passwort', 'New password')}
            autoComplete="new-password"
            size="md"
            autoFocus
            {...form.getInputProps('password')}
          />
          <PasswordInput
            label={tr('Passwort wiederholen', 'Confirm password')}
            autoComplete="new-password"
            size="md"
            {...form.getInputProps('confirm')}
          />
          <Button type="submit" size="md" fullWidth loading={loading}>
            {tr('Passwort speichern', 'Set new password')}
          </Button>
          <Button
            variant="subtle"
            fullWidth
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/login')}
          >
            {tr('Zurück zur Anmeldung', 'Back to sign in')}
          </Button>
        </Stack>
      </form>
    </AuthFrame>
  )
}
