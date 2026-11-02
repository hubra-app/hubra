import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Center, Loader, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconCircleCheck, IconFingerprint } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import * as authApi from '@/api/auth'
import { useLang } from '@/lang'
import { getPasskey, passkeyCancelled, passkeysSupported } from '@/webauthn'

/** What manage listens for (window.opener.postMessage). */
const MESSAGE = 'hubra:step-up'
/** The signed state of a challenge lives five minutes; fetch a new one before. */
const OPTIONS_MAX_AGE_MS = 4 * 60 * 1000

interface Ceremony {
  options: Record<string, unknown>
  state: string
  at: number
}

/**
 * Confirm a platform action with a passkey (opened by manage's
 * "Passwort bestätigen" dialog in a small window).
 *
 * Passkeys belong to this portal's address, so manage cannot ask for one
 * itself; it opens this page instead. The confirmation counts for this
 * sign-in (manage and this page share it), for the same ten minutes as the
 * password. Manage notices by itself; the message to the opener only makes
 * it quicker.
 */
export function ConfirmScreen() {
  const { authStatus, urls } = useSso()
  const navigate = useNavigate()
  const { tr } = useLang()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const ceremony = useRef<Ceremony | null>(null)

  useEffect(() => {
    if (authStatus === 'anon')
      navigate(`/login?redirect=${encodeURIComponent(window.location.href)}`, { replace: true })
  }, [authStatus, navigate])

  const status = useQuery({
    queryKey: ['step-up'],
    queryFn: ({ signal }) => authApi.getStepUpStatus(signal),
    enabled: authStatus === 'authed',
    retry: false,
  })

  const prepare = useCallback(async () => {
    ceremony.current = { ...(await authApi.stepUpPasskeyOptions()), at: Date.now() }
    return ceremony.current
  }, [])

  // Fetched ahead, so the browser's passkey prompt opens straight from the
  // click (Safari wants it inside the click).
  useEffect(() => {
    if (status.data?.passkey && !ceremony.current) prepare().catch(() => undefined)
  }, [status.data, prepare])

  const tellManage = () => {
    try {
      window.opener?.postMessage({ type: MESSAGE, ok: true }, new URL(urls.manage).origin)
    } catch {
      // No opener (opened directly) or a different manage address: manage
      // still notices through its own check.
    }
  }

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      let start = ceremony.current
      if (!start || Date.now() - start.at > OPTIONS_MAX_AGE_MS) start = await prepare()
      ceremony.current = null
      const credential = await getPasskey(start.options)
      await authApi.stepUpWithPasskey(start.state, credential)
      setDone(true)
      tellManage()
      // Some browsers refuse to close a window the page did not open itself.
      setTimeout(() => window.close(), 1200)
    } catch (err) {
      if (!passkeyCancelled(err)) {
        const code = (err as { code?: string }).code
        setError(
          code === 'PASSKEY_INVALID'
            ? tr(
                'Dieser Passkey gehört nicht zu deinem Konto oder ist abgelaufen. Versuch es nochmals.',
                'This passkey does not belong to your account, or the request expired. Try again.',
              )
            : ((err as Error).message ?? tr('Bestätigung fehlgeschlagen', 'Confirmation failed')),
        )
      }
      prepare().catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  if (authStatus !== 'authed' || status.isLoading)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  const noPasskey = status.isError || !status.data?.passkey
  return (
    <SignedInFrame width={460}>
      <Paper withBorder radius="md" p="xl">
        <Stack gap="md">
          <ThemeIcon size={48} radius="xl" variant="light" color={done ? 'green' : undefined}>
            {done ? <IconCircleCheck size={26} /> : <IconFingerprint size={26} />}
          </ThemeIcon>
          {done ? (
            <div>
              <Title order={2} mb={6}>
                {tr('Bestätigt', 'Confirmed')}
              </Title>
              <Text size="sm" c="dimmed">
                {tr(
                  'Die Verwaltung macht jetzt weiter. Du kannst dieses Fenster schliessen.',
                  'Manage carries on now. You can close this window.',
                )}
              </Text>
            </div>
          ) : (
            <>
              <div>
                <Title order={2} mb={6}>
                  {tr('Aktion bestätigen', 'Confirm the action')}
                </Title>
                <Text size="sm" c="dimmed">
                  {tr(
                    'Die Verwaltung (Hubra Manage) möchte eine Aktion ausführen, die tief in die Plattform eingreift. Bestätige mit deinem Passkey; das gilt dann zehn Minuten für diese Anmeldung.',
                    'Manage (Hubra Manage) wants to run an action that cuts deep into the platform. Confirm with your passkey; that holds for ten minutes on this sign-in.',
                  )}
                </Text>
              </div>
              {noPasskey ? (
                <Alert color="orange">
                  {tr(
                    'Dein Konto hat keinen Passkey. Bestätige in der Verwaltung mit deinem Passwort.',
                    'Your account has no passkey. Confirm with your password in manage.',
                  )}
                </Alert>
              ) : !passkeysSupported() ? (
                <Alert color="orange">
                  {tr(
                    'Dieser Browser kann keine Passkeys verwenden. Bestätige in der Verwaltung mit deinem Passwort.',
                    'This browser cannot use passkeys. Confirm with your password in manage.',
                  )}
                </Alert>
              ) : (
                <Button
                  size="md"
                  leftSection={<IconFingerprint size={18} />}
                  onClick={confirm}
                  loading={busy}
                >
                  {tr('Mit Passkey bestätigen', 'Confirm with a passkey')}
                </Button>
              )}
              {error && (
                <Alert color="red" py="xs">
                  {error}
                </Alert>
              )}
            </>
          )}
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}
