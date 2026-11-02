import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Divider,
  getDefaultZIndex,
  Group,
  Loader,
  Modal,
  PasswordInput,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { IconFingerprint, IconShieldLock } from '@tabler/icons-react'
import { SSO_URL } from '@hubra/api-client'
import {
  getStepUpStatus,
  openPasskeyConfirm,
  setStepUpHandler,
  STEP_UP_MESSAGE,
  stepUp,
  type StepUpStatus,
} from '@/api/stepUp'
import { tr } from '@/lang'

/** How often manage asks whether the passkey window confirmed. */
const POLL_MS = 1500

/** Mounted once in App: registers the step-up handler that `withStepUp`
 * opens when the backend answers 403 STEP_UP_REQUIRED. The person confirms
 * with a passkey (on the SSO portal, in a small window) or with their
 * password (and the app code, with two-factor on), which holds for ten
 * minutes; the wrapped call then runs again. */
export function StepUpDialog() {
  const [opened, setOpened] = useState(false)
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [needsCode, setNeedsCode] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<StepUpStatus | null>(null)
  const [waiting, setWaiting] = useState(false)
  const resolver = useRef<((ok: boolean) => void) | null>(null)
  const popup = useRef<Window | null>(null)

  useEffect(() => {
    setStepUpHandler(
      () =>
        new Promise<boolean>((resolve) => {
          resolver.current?.(false)
          resolver.current = resolve
          setPassword('')
          setCode('')
          setError(null)
          setWaiting(false)
          setStatus(null)
          setOpened(true)
          // Offer the passkey only to accounts that have one; the password
          // form works meanwhile and stays the fallback.
          getStepUpStatus()
            .then(setStatus)
            .catch(() => setStatus({ sudoUntil: null, passkey: false, code: false }))
        }),
    )
    return () => setStepUpHandler(null)
  }, [])

  const close = (ok: boolean) => {
    setOpened(false)
    setWaiting(false)
    if (popup.current && !popup.current.closed) {
      try {
        popup.current.close()
      } catch {
        // Cross-origin windows may refuse; it closes itself after confirming.
      }
    }
    popup.current = null
    resolver.current?.(ok)
    resolver.current = null
  }

  // While the passkey window is open: ask the API whether this sign-in is
  // confirmed now (works whatever the window can tell us), and take the
  // window's message as a hint to ask right away.
  useEffect(() => {
    if (!waiting) return
    let stopped = false
    const check = async () => {
      try {
        const now = await getStepUpStatus()
        if (!stopped && now.sudoUntil) close(true)
      } catch {
        // Keep waiting; the password form is still there.
      }
    }
    const timer = window.setInterval(check, POLL_MS)
    const ssoOrigin = new URL(SSO_URL, window.location.href).origin
    const onMessage = (e: MessageEvent) => {
      if (e.origin === ssoOrigin && (e.data as { type?: string } | null)?.type === STEP_UP_MESSAGE) check()
    }
    window.addEventListener('message', onMessage)
    return () => {
      stopped = true
      window.clearInterval(timer)
      window.removeEventListener('message', onMessage)
    }
  }, [waiting])

  const usePasskey = () => {
    setError(null)
    // Opened straight from the click, or the browser blocks the window.
    const w = openPasskeyConfirm(SSO_URL)
    if (!w) {
      setError(
        tr(
          'Das Fenster für den Passkey wurde blockiert. Erlaube Pop-ups für diese Seite oder bestätige mit deinem Passwort.',
          'The passkey window was blocked. Allow pop-ups for this site, or confirm with your password.',
        ),
      )
      return
    }
    popup.current = w
    setWaiting(true)
  }

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      await stepUp(password, needsCode && code ? code : undefined)
      close(true)
    } catch (err) {
      const e = err as { code?: string; message?: string }
      if (e.code === 'MFA_INVALID' && !needsCode) {
        // Two-factor is on: the password alone is not enough here.
        setNeedsCode(true)
        setError(
          status?.code
            ? tr('Gib auch den Code aus deiner Authenticator-App ein.', 'Also enter the code from your authenticator app.')
            : tr('Gib auch einen Wiederherstellungscode ein.', 'Also enter a recovery code.'),
        )
      } else {
        setError(e.message ?? tr('Bestätigung fehlgeschlagen', 'Confirmation failed'))
      }
    } finally {
      setLoading(false)
    }
  }

  const passkey = !!status?.passkey
  return (
    <Modal
      opened={opened}
      onClose={() => close(false)}
      title={
        <Group gap="xs">
          <IconShieldLock size={18} />
          <Text fw={600}>
            {passkey ? tr('Aktion bestätigen', 'Confirm this action') : tr('Passwort bestätigen', 'Confirm your password')}
          </Text>
        </Group>
      }
      size="sm"
      centered
      // It opens on top of the dialog that asked for it (delete or restore a
      // backup, …); every Modal shares one z-index, so without this it can
      // end up underneath, out of reach.
      zIndex={getDefaultZIndex('max')}
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {passkey
            ? tr(
                'Diese Aktion greift tief in die Plattform ein. Bestätige mit deinem Passkey oder deinem Passwort; das gilt dann zehn Minuten.',
                'This action cuts deep into the platform. Confirm with your passkey or your password; that holds for ten minutes.',
              )
            : tr(
                'Diese Aktion greift tief in die Plattform ein. Bestätige dein Passwort; das gilt dann zehn Minuten.',
                'This action cuts deep into the platform. Confirm your password; that holds for ten minutes.',
              )}
        </Text>
        {passkey && (
          <>
            {waiting ? (
              <Alert color="acc" py="xs" icon={<Loader size={16} />}>
                <Group justify="space-between" gap="xs" wrap="nowrap">
                  <Text size="sm">
                    {tr('Bestätige im Passkey-Fenster …', 'Confirm in the passkey window …')}
                  </Text>
                  <Button size="compact-xs" variant="subtle" onClick={usePasskey}>
                    {tr('Erneut öffnen', 'Open again')}
                  </Button>
                </Group>
              </Alert>
            ) : (
              <Button leftSection={<IconFingerprint size={18} />} onClick={usePasskey} data-autofocus>
                {tr('Mit Passkey bestätigen', 'Confirm with a passkey')}
              </Button>
            )}
            <Divider label={tr('oder mit Passwort', 'or with your password')} labelPosition="center" />
          </>
        )}
        <PasswordInput
          label={tr('Passwort', 'Password')}
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus={!passkey}
          data-autofocus={passkey ? undefined : true}
        />
        {needsCode && (
          <TextInput
            label={
              status?.code
                ? tr('Code aus der Authenticator-App', 'Code from the authenticator app')
                : tr('Wiederherstellungscode', 'Recovery code')
            }
            value={code}
            onChange={(e) => setCode(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder={status?.code ? '123456' : undefined}
            inputMode={status?.code ? 'numeric' : undefined}
          />
        )}
        {error && (
          <Alert color="red" py="xs">
            {error}
          </Alert>
        )}
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={() => close(false)} disabled={loading}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button variant={passkey ? 'light' : 'filled'} onClick={submit} loading={loading} disabled={!password}>
            {tr('Mit Passwort bestätigen', 'Confirm with password')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
