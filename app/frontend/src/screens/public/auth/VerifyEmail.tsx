import { useEffect, useRef, useState } from 'react'
import { Button, Loader, Stack, Text, Title, ThemeIcon } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { IconCheck, IconCircleX } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { AuthFrame } from './AuthFrame'

type State = 'verifying' | 'success' | 'error'

/** Opened from the verification mail: /verify-email#token=… */
export function VerifyEmailScreen() {
  const navigate = useNavigate()
  const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token')
  const [state, setState] = useState<State>(token ? 'verifying' : 'error')
  const [message, setMessage] = useState(token ? '' : 'The verification link is incomplete.')
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
        setMessage(err instanceof Error ? err.message : 'Verification failed.')
      })
  }, [token])

  return (
    <AuthFrame>
      <Stack align="center" ta="center" gap="xs">
        {state === 'verifying' && (
          <>
            <Loader />
            <Title order={2}>Verifying email…</Title>
          </>
        )}
        {state === 'success' && (
          <>
            <ThemeIcon size={56} radius="xl" color="green" variant="light">
              <IconCheck size={28} />
            </ThemeIcon>
            <Title order={2}>Email verified</Title>
            <Text size="sm" c="dimmed" mb="md">
              Your email address is confirmed.
            </Text>
          </>
        )}
        {state === 'error' && (
          <>
            <ThemeIcon size={56} radius="xl" color="red" variant="light">
              <IconCircleX size={28} />
            </ThemeIcon>
            <Title order={2}>Verification failed</Title>
            <Text size="sm" c="dimmed" mb="md">
              {message}
            </Text>
          </>
        )}
        {state !== 'verifying' && (
          <Button fullWidth onClick={() => navigate('/')}>
            Continue
          </Button>
        )}
      </Stack>
    </AuthFrame>
  )
}
