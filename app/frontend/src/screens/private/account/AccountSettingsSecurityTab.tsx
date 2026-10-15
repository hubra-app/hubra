import { useState } from 'react'
import { Alert, Button, Group, Paper, PasswordInput, Text } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconCheck, IconLock } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useToast } from '@/context/AppContext'
import { Field } from '@/components/ui'
import { useT } from '@/locales/i18n'

const passwordSchema = z
  .object({
    currentPw: z.string().min(1, 'Current password is required'),
    newPw: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPw: z.string().min(8, 'Password must be at least 8 characters'),
  })
  .refine((data) => data.newPw === data.confirmPw, {
    message: 'Passwords do not match',
    path: ['confirmPw'],
  })
type PasswordForm = z.infer<typeof passwordSchema>

export function AccountSettingsSecurityTab() {
  const { t } = useT()
  const { notify } = useToast()

  const [pwLoading, setPwLoading] = useState(false)

  const passwordForm = useForm<PasswordForm>({
    validate: zodResolver(passwordSchema),
    initialValues: { currentPw: '', newPw: '', confirmPw: '' },
  })

  const handleChangePassword = async (data: PasswordForm) => {
    setPwLoading(true)
    try {
      await authApi.changePassword(data.currentPw, data.newPw)
      passwordForm.reset()
      notify(
        'success',
        t('account.password.changed', 'Passwort gändert'),
        t(
          'account.password.updatedMsg',
          'Din Passwort isch aktualisiert worde.',
        ),
      )
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : t(
              'account.failedToChangePassword',
              'Passwortänderig fehlgeschlage.',
            )
      passwordForm.setFieldError('root', msg)
      notify(
        'error',
        t('account.password.changeFailed', 'Passwortänderig fehlgeschlage'),
        msg,
      )
    } finally {
      setPwLoading(false)
    }
  }

  return (
    <>
      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <IconLock size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
          <Text fw={700} fz="md">
            {t('account.changePassword', 'Passwort ändere')}
          </Text>
        </Group>
        <div
          style={{
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {(passwordForm.errors.root ||
            passwordForm.errors.currentPw ||
            passwordForm.errors.newPw ||
            passwordForm.errors.confirmPw) && (
            <Alert color="red" variant="light">
              {passwordForm.errors.root ??
                passwordForm.errors.currentPw ??
                passwordForm.errors.newPw ??
                passwordForm.errors.confirmPw}
            </Alert>
          )}
          <Field label={t('account.currentPassword', 'Aktuells Passwort')}>
            <PasswordInput {...passwordForm.getInputProps('currentPw')} />
          </Field>
          <Field
            label={t('account.newPassword', 'Neus Passwort')}
            hint={t('account.minimum8chars', 'Mindestens 8 Zeiche')}
          >
            <PasswordInput {...passwordForm.getInputProps('newPw')} />
          </Field>
          <Field
            label={t('account.confirmNewPassword', 'Neus Passwort bestätige')}
          >
            <PasswordInput {...passwordForm.getInputProps('confirmPw')} />
          </Field>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="filled"
              onClick={() => passwordForm.onSubmit(handleChangePassword)()}
              disabled={pwLoading}
            >
              <IconCheck size={16} />
              {pwLoading
                ? t('account.updating', 'Wird aktualisiert…')
                : t('account.updatePassword', 'Passwort aktualisiere')}
            </Button>
          </div>
        </div>
      </Paper>
    </>
  )
}
