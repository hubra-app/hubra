import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Group, Modal, PasswordInput, Stack, Text, TextInput } from '@mantine/core'
import { IconShieldLock } from '@tabler/icons-react'
import { setStepUpHandler, stepUp } from '@/api/stepUp'
import { tr } from '@/lang'

/** Mounted once in App: registers the step-up handler that `withStepUp`
 * opens when the backend answers 403 STEP_UP_REQUIRED. The person confirms
 * their password (and the app code, with two-factor on), which holds for a
 * few minutes; the wrapped call then runs again. */
export function StepUpDialog() {
  const [opened, setOpened] = useState(false)
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [needsCode, setNeedsCode] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const resolver = useRef<((ok: boolean) => void) | null>(null)

  useEffect(() => {
    setStepUpHandler(
      () =>
        new Promise<boolean>((resolve) => {
          resolver.current?.(false)
          resolver.current = resolve
          setPassword('')
          setCode('')
          setError(null)
          setOpened(true)
        }),
    )
    return () => setStepUpHandler(null)
  }, [])

  const close = (ok: boolean) => {
    setOpened(false)
    resolver.current?.(ok)
    resolver.current = null
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
        setError(tr('Gib auch den Code aus deiner Authenticator-App ein.', 'Also enter the code from your authenticator app.'))
      } else {
        setError(e.message ?? tr('Bestätigung fehlgeschlagen', 'Confirmation failed'))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={() => close(false)}
      title={
        <Group gap="xs">
          <IconShieldLock size={18} />
          <Text fw={600}>{tr('Passwort bestätigen', 'Confirm your password')}</Text>
        </Group>
      }
      size="sm"
      centered
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {tr(
            'Diese Aktion greift tief in die Plattform ein. Bestätige dein Passwort; das gilt dann ein paar Minuten.',
            'This action cuts deep into the platform. Confirm your password; that holds for a few minutes.',
          )}
        </Text>
        <PasswordInput
          label={tr('Passwort', 'Password')}
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus
          data-autofocus
        />
        {needsCode && (
          <TextInput
            label={tr('Code aus der Authenticator-App', 'Code from the authenticator app')}
            value={code}
            onChange={(e) => setCode(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="123456"
            inputMode="numeric"
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
          <Button onClick={submit} loading={loading} disabled={!password}>
            {tr('Bestätigen', 'Confirm')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
