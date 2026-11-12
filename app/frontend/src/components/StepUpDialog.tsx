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
import {
  getStepUpStatus,
  openPasskeyConfirm,
  setStepUpHandler,
  STEP_UP_MESSAGE,
  stepUp,
  type StepUpStatus,
} from '@/api/stepUp'
import { useInstance } from '@/context/InstanceContext'
import { useT } from '@/locales/i18n'

/** How often the app asks whether the passkey window confirmed. */
const POLL_MS = 1500

/** Mounted once in the shell: registers the step-up handler that `withStepUp`
 * opens when the backend answers 403 STEP_UP_REQUIRED. The person confirms
 * with a passkey (on the SSO portal, in a small window) or with their
 * password (and the app code, with two-factor on), which holds for ten
 * minutes; the wrapped call then runs again. */
export function StepUpDialog() {
  const { t } = useT()
  const { ssoUrl } = useInstance()
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
    const ssoOrigin = new URL(ssoUrl, window.location.href).origin
    const onMessage = (e: MessageEvent) => {
      if (e.origin === ssoOrigin && (e.data as { type?: string } | null)?.type === STEP_UP_MESSAGE) check()
    }
    window.addEventListener('message', onMessage)
    return () => {
      stopped = true
      window.clearInterval(timer)
      window.removeEventListener('message', onMessage)
    }
  }, [waiting, ssoUrl])

  const usePasskey = () => {
    setError(null)
    // Opened straight from the click, or the browser blocks the window.
    const w = openPasskeyConfirm(ssoUrl)
    if (!w) {
      setError(
        t(
          'stepUp.popupBlocked',
          'Das Fenster für den Passkey wurde blockiert. Erlaube Pop-ups für diese Seite oder bestätige mit deinem Passwort.',
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
            ? t('stepUp.alsoCode', 'Gib auch den Code aus deiner Authenticator-App ein.')
            : t('stepUp.alsoRecovery', 'Gib auch einen Wiederherstellungscode ein.'),
        )
      } else {
        setError(e.message ?? t('stepUp.failed', 'Bestätigung fehlgeschlagen'))
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
            {passkey ? t('stepUp.titleAction', 'Aktion bestätigen') : t('stepUp.titlePassword', 'Passwort bestätigen')}
          </Text>
        </Group>
      }
      size="sm"
      centered
      // It opens on top of the dialog that asked for it; every Modal shares
      // one z-index, so without this it can end up underneath, out of reach.
      zIndex={getDefaultZIndex('max')}
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {passkey
            ? t(
                'stepUp.hintPasskey',
                'Diese Aktion lässt sich schwer rückgängig machen (Bankdaten, Admin-Rechte, endgültig löschen). Bestätige mit deinem Passkey oder deinem Passwort; das gilt dann zehn Minuten.',
              )
            : t(
                'stepUp.hintPassword',
                'Diese Aktion lässt sich schwer rückgängig machen (Bankdaten, Admin-Rechte, endgültig löschen). Bestätige dein Passwort; das gilt dann zehn Minuten.',
              )}
        </Text>
        {passkey && (
          <>
            {waiting ? (
              <Alert color="violet" py="xs" icon={<Loader size={16} />}>
                <Group justify="space-between" gap="xs" wrap="nowrap">
                  <Text size="sm">
                    {t('stepUp.waiting', 'Bestätige im Passkey-Fenster …')}
                  </Text>
                  <Button size="compact-xs" variant="subtle" onClick={usePasskey}>
                    {t('stepUp.openAgain', 'Erneut öffnen')}
                  </Button>
                </Group>
              </Alert>
            ) : (
              <Button leftSection={<IconFingerprint size={18} />} onClick={usePasskey} data-autofocus>
                {t('stepUp.withPasskey', 'Mit Passkey bestätigen')}
              </Button>
            )}
            <Divider label={t('stepUp.orPassword', 'oder mit Passwort')} labelPosition="center" />
          </>
        )}
        <PasswordInput
          label={t('stepUp.password', 'Passwort')}
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
                ? t('stepUp.code', 'Code aus der Authenticator-App')
                : t('stepUp.recovery', 'Wiederherstellungscode')
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
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant={passkey ? 'light' : 'filled'} onClick={submit} loading={loading} disabled={!password}>
            {t('stepUp.withPassword', 'Mit Passwort bestätigen')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
