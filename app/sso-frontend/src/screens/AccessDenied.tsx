import { Button, Stack, Text, Title } from '@mantine/core'
import { IconArrowLeft, IconShieldX } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { AuthFrame, AuthIcon } from '@/components/AuthFrame'
import { useLang } from '@/lang'

export function AccessDenied() {
  const navigate = useNavigate()
  const { tr } = useLang()
  const cosUrl = import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club'

  return (
    <AuthFrame>
      <AuthIcon tone="red">
        <IconShieldX size={26} color="#b91c1c" />
      </AuthIcon>
      <Title order={1} fz={30} mb={8}>
        {tr('Kein Zugriff', 'Access denied')}
      </Title>
      <Text c="dimmed" mb={28} lh={1.6}>
        {tr(
          'Du bist angemeldet, aber dein Konto hat keine Berechtigung für die Plattform-Verwaltung.',
          'You are signed in, but your account may not use the platform admin portal.',
        )}
      </Text>
      <Stack gap="xs">
        <Button size="md" fullWidth onClick={() => window.location.assign(cosUrl)}>
          {tr('Zu meinen Vereinen', 'Go to my clubs')}
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
    </AuthFrame>
  )
}
