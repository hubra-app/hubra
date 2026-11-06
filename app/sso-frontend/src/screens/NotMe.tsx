import { useState } from 'react'
import { Button, Center, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { IconCircleX, IconShieldCheck, IconShieldLock } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useLang } from '@/lang'

type State = 'ask' | 'busy' | 'done' | 'error'

/** "This wasn't me" from a new-device alert (mail or Discord):
 * /not-me#token=…  It asks first (mail scanners open links), then ends
 * every session of the account and leads to a new password. */
export function NotMe() {
  const navigate = useNavigate()
  const { tr } = useLang()
  const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token')
  const [state, setState] = useState<State>(token ? 'ask' : 'error')
  const [message, setMessage] = useState(
    token ? '' : tr('Der Link ist unvollständig.', 'The link is incomplete.'),
  )

  const endAll = async () => {
    if (!token) return
    setState('busy')
    try {
      await authApi.notMe(token)
      setState('done')
    } catch (err) {
      setState('error')
      setMessage(
        err instanceof Error && err.message
          ? err.message
          : tr('Der Link ist ungültig oder abgelaufen.', 'The link is invalid or has expired.'),
      )
    }
  }

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex' }}>
      <Center flex={1} p={24}>
        <Paper withBorder p="xl" maw={440} w="100%">
          <Stack align="center" ta="center" gap="xs">
            {(state === 'ask' || state === 'busy') && (
              <>
                <ThemeIcon size={56} radius="xl" color="orange" variant="light">
                  <IconShieldLock size={24} />
                </ThemeIcon>
                <Title order={2}>{tr('Das warst nicht du?', "That wasn't you?")}</Title>
                <Text size="sm" c="dimmed" mb="md">
                  {tr(
                    'Wir beenden sofort jede Anmeldung bei deinem Konto, auf allen Geräten. Danach setzt du ein neues Passwort.',
                    'We end every sign-in to your account at once, on every device. Then you set a new password.',
                  )}
                </Text>
                <Button color="red" fullWidth loading={state === 'busy'} onClick={endAll}>
                  {tr('Alle Anmeldungen beenden', 'End all sign-ins')}
                </Button>
              </>
            )}
            {state === 'done' && (
              <>
                <ThemeIcon size={56} radius="xl" color="green" variant="light">
                  <IconShieldCheck size={24} />
                </ThemeIcon>
                <Title order={2}>{tr('Alle Anmeldungen beendet', 'All sign-ins ended')}</Title>
                <Text size="sm" c="dimmed" mb="md">
                  {tr(
                    'Setze jetzt ein neues Passwort. Hast du Zwei-Faktor noch nicht an, schalte es danach ein.',
                    "Now set a new password. If two-factor isn't on yet, turn it on afterwards.",
                  )}
                </Text>
                <Button fullWidth onClick={() => navigate('/forgot-password')}>
                  {tr('Neues Passwort setzen', 'Set a new password')}
                </Button>
              </>
            )}
            {state === 'error' && (
              <>
                <ThemeIcon size={56} radius="xl" color="red" variant="light">
                  <IconCircleX size={24} />
                </ThemeIcon>
                <Title order={2}>{tr('Das ging nicht', "That didn't work")}</Title>
                <Text size="sm" c="dimmed" mb="md">
                  {message}{' '}
                  {tr(
                    'Ändere dein Passwort, das beendet ebenfalls alle Anmeldungen.',
                    'Change your password; that ends every sign-in too.',
                  )}
                </Text>
                <Button fullWidth onClick={() => navigate('/forgot-password')}>
                  {tr('Passwort zurücksetzen', 'Reset password')}
                </Button>
              </>
            )}
          </Stack>
        </Paper>
      </Center>
    </div>
  )
}
