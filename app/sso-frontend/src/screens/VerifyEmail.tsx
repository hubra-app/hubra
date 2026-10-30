import { useEffect, useRef, useState } from 'react'
import { Button, Center, Loader, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { IconCheck, IconCircleX } from '@tabler/icons-react'
import { useSso } from '@/context/SsoContext'
import * as authApi from '@/api/auth'
import { useLang } from '@/lang'

type State = 'verifying' | 'success' | 'error'

/** Opened from the verification mail: /verify-email#token=… */
export function VerifyEmail() {
  const { authStatus, continueSignedIn } = useSso()
  const navigate = useNavigate()
  const { tr } = useLang()
  const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token')
  const [state, setState] = useState<State>(token ? 'verifying' : 'error')
  const [message, setMessage] = useState(
    token ? '' : tr('Der Link ist unvollständig.', 'The link is incomplete.'),
  )
  // Tokens are single-use: StrictMode's double effect must not spend it twice.
  const sent = useRef(false)

  useEffect(() => {
    if (!token || sent.current) return
    sent.current = true
    authApi
      .verifyEmail(token)
      .then(() => setState('success'))
      .catch((err: unknown) => {
        setState('error')
        setMessage(
          err instanceof Error && err.message
            ? err.message
            : tr('Der Link ist ungültig oder abgelaufen.', 'The link is invalid or has expired.'),
        )
      })
  }, [token])

  const signedIn = authStatus === 'authed'

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex' }}>
      <Center flex={1} p={24}>
        <Paper withBorder radius="md" p="xl" maw={420} w="100%">
          <Stack align="center" ta="center" gap="xs">
            {state === 'verifying' && (
              <>
                <Loader />
                <Title order={2}>{tr('E-Mail wird bestätigt…', 'Confirming email…')}</Title>
              </>
            )}
            {state === 'success' && (
              <>
                <ThemeIcon size={56} radius="xl" color="green" variant="light">
                  <IconCheck size={28} />
                </ThemeIcon>
                <Title order={2}>{tr('E-Mail bestätigt', 'Email confirmed')}</Title>
                <Text size="sm" c="dimmed" mb="md">
                  {tr('Danke, deine Adresse ist bestätigt.', 'Thanks, your address is confirmed.')}
                </Text>
              </>
            )}
            {state === 'error' && (
              <>
                <ThemeIcon size={56} radius="xl" color="red" variant="light">
                  <IconCircleX size={28} />
                </ThemeIcon>
                <Title order={2}>{tr('Bestätigung fehlgeschlagen', 'Confirmation failed')}</Title>
                <Text size="sm" c="dimmed" mb="md">
                  {message}{' '}
                  {tr(
                    'Melde dich an, um einen neuen Link zu erhalten.',
                    'Sign in to get a new link.',
                  )}
                </Text>
              </>
            )}
            {state !== 'verifying' &&
              (authStatus === 'loading' ? (
                <Loader size="sm" />
              ) : signedIn ? (
                <Button fullWidth onClick={continueSignedIn}>
                  {tr('Weiter', 'Continue')}
                </Button>
              ) : (
                <Button fullWidth onClick={() => navigate('/login')}>
                  {tr('Zur Anmeldung', 'Go to sign-in')}
                </Button>
              ))}
          </Stack>
        </Paper>
      </Center>
    </div>
  )
}
