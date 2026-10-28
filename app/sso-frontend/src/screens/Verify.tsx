import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Anchor,
  Button,
  Center,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconMailCheck } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import * as authApi from '@/api/auth'

const RESEND_COOLDOWN_S = 60

/**
 * The step after sign-in while the private email is unconfirmed: the link
 * goes out, the page waits for it (also when it's opened in another tab),
 * and the person can resend it or fix a mistyped address.
 */
export function VerifyScreen() {
  const { authStatus, continueSignedIn, notify } = useSso()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const autoSent = useRef(false)
  const [cooldown, setCooldown] = useState(0)
  const [sending, setSending] = useState(false)
  const [changing, setChanging] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (authStatus === 'anon') navigate('/login', { replace: true })
  }, [authStatus, navigate])

  const status = useQuery({
    queryKey: ['email-verification'],
    queryFn: ({ signal }) => authApi.getVerificationStatus(signal),
    enabled: authStatus === 'authed',
    // Picks up a link confirmed in another tab or on the phone.
    refetchInterval: 5000,
  })

  const done = status.data && !status.data.required
  useEffect(() => {
    if (done) continueSignedIn()
  }, [done, continueSignedIn])

  useEffect(() => {
    if (cooldown <= 0) return
    const id = setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => clearTimeout(id)
  }, [cooldown])

  const send = async (quiet = false) => {
    setSending(true)
    try {
      await authApi.sendVerificationEmail()
      setCooldown(RESEND_COOLDOWN_S)
      await queryClient.invalidateQueries({ queryKey: ['email-verification'] })
      if (!quiet) notify('success', 'Link gesendet', 'Schau in deinem Posteingang nach.')
    } catch (err: unknown) {
      notify('error', 'Senden fehlgeschlagen', err instanceof Error ? err.message : undefined)
    } finally {
      setSending(false)
    }
  }

  // The first link goes out by itself, unless one is already on its way.
  useEffect(() => {
    if (!status.data?.required || status.data.sentAt || autoSent.current) return
    autoSent.current = true
    send(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.data])

  const saveEmail = async () => {
    setError('')
    setSaving(true)
    try {
      const next = await authApi.changeEmail(newEmail.trim().toLowerCase(), password)
      queryClient.setQueryData(['email-verification'], next)
      setChanging(false)
      setPassword('')
      setCooldown(RESEND_COOLDOWN_S)
      notify('success', 'Adresse geändert', `Wir haben einen neuen Link an ${next.email} gesendet.`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ändern fehlgeschlagen')
    } finally {
      setSaving(false)
    }
  }

  if (!status.data || done)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  return (
    <SignedInFrame width={460}>
      <Paper withBorder radius="md" p="xl">
        <Stack gap="md">
          <ThemeIcon size={48} radius="xl" variant="light">
            <IconMailCheck size={26} />
          </ThemeIcon>
          <div>
            <Title order={2} mb={6}>
              Bestätige deine E-Mail-Adresse
            </Title>
            <Text size="sm" c="dimmed">
              Wir haben einen Link an <b>{status.data.email}</b> gesendet. Öffne ihn, dann geht es
              hier automatisch weiter. Der Link ist 24 Stunden gültig.
            </Text>
          </div>

          <Button variant="light" loading={sending} disabled={cooldown > 0} onClick={() => send()}>
            {cooldown > 0 ? `Erneut senden (${cooldown} s)` : 'Link erneut senden'}
          </Button>

          {!changing ? (
            <Text size="sm" c="dimmed">
              Falsche Adresse?{' '}
              <Anchor
                component="button"
                type="button"
                size="sm"
                onClick={() => {
                  setNewEmail(status.data.email)
                  setChanging(true)
                }}
              >
                Adresse ändern
              </Anchor>
            </Text>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                saveEmail()
              }}
            >
              <Stack gap="sm">
                {error && (
                  <Alert color="red" variant="light">
                    {error}
                  </Alert>
                )}
                <TextInput
                  label="Neue E-Mail-Adresse"
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.currentTarget.value)}
                />
                <PasswordInput
                  label="Aktuelles Passwort"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.currentTarget.value)}
                />
                <Button type="submit" loading={saving}>
                  Speichern und Link senden
                </Button>
                <Button variant="subtle" onClick={() => setChanging(false)}>
                  Abbrechen
                </Button>
              </Stack>
            </form>
          )}
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}
