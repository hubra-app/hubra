import { useState } from 'react'
import {
  Modal,
  Stack,
  PasswordInput,
  Button,
  Alert,
  Group,
  Text,
  ThemeIcon,
} from '@mantine/core'
import { IconLock, IconAlertTriangle } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { changePassword } from '@/api/auth'

export function ForcedPasswordChangeModal() {
  const { t } = useT()
  const { clearMustChangePassword } = useAuth()
  const { notify } = useToast()
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    setError('')
    if (!currentPw || !newPw) {
      setError(
        t('account.password.change.text', 'Gib dein aktuelles und dein neues Passwort ein.'),
      )
      return
    }
    if (newPw.length < 8) {
      setError(
        t(
          'account.password.minLength',
          'Das neue Passwort muss mindestens 8 Zeichen lang sein.',
        ),
      )
      return
    }
    if (newPw !== confirmPw) {
      setError(
        t('account.passwordsDoNotMatch', 'Die neuen Passwörter stimmen nicht überein.'),
      )
      return
    }
    setLoading(true)
    try {
      await changePassword(currentPw, newPw)
      clearMustChangePassword()
      notify(
        'success',
        t('account.password.changed', 'Passwort geändert'),
        t(
          'account.password.updatedMsg',
          'Dein Passwort wurde geändert.',
        ),
      )
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : t(
              'account.failedToChangePassword',
              'Passwort konnte nicht geändert werden.',
            )
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      opened
      onClose={() => {}}
      closeOnClickOutside={false}
      closeOnEscape={false}
      withCloseButton={false}
      centered
      size="sm"
    >
      <Group gap="sm" mb="md" align="center">
        <ThemeIcon size={44} radius="md" color="yellow" variant="light">
          <IconAlertTriangle size={22} />
        </ThemeIcon>
        <Stack gap={2}>
          <Text fz={17} fw={700}>
            {t('account.must.change.passwordLabel', 'Passwort muss geändert werden')}
          </Text>
          <Text size="sm" c="dimmed">
            {t(
              'account.must.change.password.desc',
              'Bitte ändere dein Passwort, um weiterzumachen.',
            )}
          </Text>
        </Stack>
      </Group>

      {error && (
        <Alert color="red" variant="light" mb="sm">
          {error}
        </Alert>
      )}

      <Stack gap="sm">
        <PasswordInput
          label={t('account.currentPassword', 'Aktuelles Passwort')}
          value={currentPw}
          onChange={(e) => setCurrentPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          autoFocus
        />
        <PasswordInput
          label={t('account.newPassword', 'Neues Passwort')}
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        />
        <PasswordInput
          label={t('account.confirm.password', 'Passwort bestätigen')}
          value={confirmPw}
          onChange={(e) => setConfirmPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        />
      </Stack>

      <Button
        fullWidth
        mt="md"
        size="md"
        leftSection={<IconLock size={16} />}
        onClick={handleSubmit}
        loading={loading}
      >
        {loading
          ? t('common.saving', 'Wird gespeichert …')
          : t('account.changePassword', 'Passwort ändern')}
      </Button>
    </Modal>
  )
}
