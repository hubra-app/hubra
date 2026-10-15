import { useState, useEffect } from 'react'
import { Button, Group, Paper, Text, TextInput, Textarea } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { IconCheck, IconMail, IconUser } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useAuth, useToast } from '@/context/AppContext'
import { Avatar, Field, Toggle } from '@/components/ui'
import { useT } from '@/locales/i18n'

const profileSchema = z.object({
  displayName: z.string().min(1, 'Display name is required'),
  email: z.string().email('Invalid email'),
  profileNote: z.string(),
  avatarColor: z.string(),
})
type ProfileForm = z.infer<typeof profileSchema>

export function AccountSettingsProfileTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, setCurrentUser } = useAuth()

  const [mailForwarding, setMailForwarding] = useState(false)
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [profileLoading, setProfileLoading] = useState(false)

  const profileForm = useForm<ProfileForm>({
    validate: zodResolver(profileSchema),
    initialValues: {
      displayName: currentUser?.name ?? '',
      email: currentUser?.email ?? '',
      profileNote: currentUser?.profileNote ?? '',
      avatarColor: currentUser?.avatarColor ?? '#6366f1',
    },
  })

  const avatarColor = profileForm.values.avatarColor

  const accountQuery = useQuery({
    queryKey: ['account'],
    queryFn: () => authApi.getAccount(),
  })
  const mailSettingsQuery = useQuery({
    queryKey: ['mail-settings'],
    queryFn: () => authApi.getMailSettings(),
  })

  const emailVerified = mailSettingsQuery.data?.private_email_verified ?? null
  const publicEmail = accountQuery.data?.publicEmail ?? ''

  useEffect(() => {
    if (accountQuery.data && !profileForm.isDirty()) {
      profileForm.setValues({
        displayName: accountQuery.data.name,
        email: accountQuery.data.email,
        profileNote: accountQuery.data.profileNote ?? '',
        avatarColor: accountQuery.data.avatarColor,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountQuery.data])

  useEffect(() => {
    if (mailSettingsQuery.data) {
      queueMicrotask(() => {
        setMailForwarding(mailSettingsQuery.data.forwarding_enabled)
      })
    }
  }, [mailSettingsQuery.data])

  const saveProfile = async (data: ProfileForm) => {
    setProfileLoading(true)
    try {
      const [first, ...rest] = data.displayName.trim().split(' ')
      const updated = await authApi.updateAccount({
        first_name: first,
        last_name: rest.join(' '),
        email: data.email,
        profile_note: data.profileNote,
        avatar_color: data.avatarColor,
      })
      setCurrentUser(updated)
      notify(
        'success',
        t('account.profile.saved', 'Profil gspeichert'),
        t('account.profile.updatedMsg', 'Din Profil isch aktualisiert worde.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('account.saveFailed', 'Speichere fehlgeschlage'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotUpdateProfile',
              'Profil chonnt nöd aktualisiert wärde.',
            ),
      )
    } finally {
      setProfileLoading(false)
    }
  }

  const toggleMailForwarding = async (val: boolean) => {
    setMailForwarding(val)
    try {
      await authApi.updateMailSettings(val)
      notify(
        'success',
        t('account.mail.saved', 'Mail-Iistellige gspeichert'),
        val
          ? t('account.forwardingEnabled', 'Witergleiti aktiviert.')
          : t('account.forwardingDisabled', 'Witergleiti deaktiviert.'),
      )
    } catch {
      setMailForwarding(!val)
      notify(
        'error',
        t('common.error', 'Fehler'),
        t(
          'account.couldNotUpdateMailSettings',
          'Mail-Iistellige chonnt nöd aktualisiert wärde.',
        ),
      )
    }
  }

  const sendVerificationEmail = async () => {
    setVerifyLoading(true)
    try {
      await authApi.requestEmailVerification()
      notify(
        'success',
        t('account.verificationEmailSent', 'Verifikations-E-Mail gsendet'),
        t('account.checkInbox', 'Überprüch din private E-Mail-Inbox.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotSendVerification',
              'Verifikations-E-Mail chonnt nöd gsendet wärde.',
            ),
      )
    } finally {
      setVerifyLoading(false)
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
          <IconUser size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
          <Text fw={700} fz="md">
            {t('account.profile', 'Profil')}
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
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              marginBottom: 4,
            }}
          >
            <Avatar
              name={currentUser?.name ?? ''}
              color={avatarColor}
              size={56}
            />
            <div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--mantine-color-ink-4)',
                  marginBottom: 6,
                }}
              >
                Avatar color
              </div>
              <input
                type="color"
                {...profileForm.getInputProps('avatarColor')}
                style={{
                  width: 48,
                  height: 36,
                  padding: '2px 4px',
                  cursor: 'pointer',
                  borderRadius: 6,
                  border: '1px solid #d3ddd7',
                }}
              />
            </div>
          </div>
          <Field label={t('common.displayName', 'Azeigename')}>
            <TextInput {...profileForm.getInputProps('displayName')} />
          </Field>
          <Field
            label={t('account.privateEmail', 'Private E-Mail')}
            hint={t(
              'account.privateEmailHint',
              'Dini persönlichi E-Mail - wird mit andere Mitglider nöd teilt',
            )}
          >
            <TextInput type="email" {...profileForm.getInputProps('email')} />
          </Field>
          <Field
            label={t('account.clubEmail', 'Club E-Mail')}
            hint={t(
              'account.clubEmailHint',
              'Automatisch generiert - kontaktier en Administrator zum ändere',
            )}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <TextInput
                value={publicEmail}
                readOnly
                styles={{
                  input: {
                    fontFamily: '"JetBrains Mono"',
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: 'var(--mantine-color-acc-8)',
                    backgroundColor: 'var(--mantine-color-acc-0)',
                    cursor: 'not-allowed',
                  },
                }}
              />
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--mantine-color-ink-3)',
                  whiteSpace: 'nowrap',
                }}
              >
                {t('account.readOnly', 'nur lese')}
              </span>
            </div>
          </Field>
          <Field
            label={t('account.profile.note', 'Profil-Notiz')}
            hint={t(
              'account.profile.noteHint',
              'Kurzi Bio oder Notiz, wo uf dim Profil azeigt wird',
            )}
          >
            <Textarea
              rows={3}
              {...profileForm.getInputProps('profileNote')}
              style={{ resize: 'vertical', minHeight: 72 }}
            />
          </Field>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="filled"
              onClick={() => profileForm.onSubmit(saveProfile)()}
              disabled={profileLoading}
            >
              <IconCheck size={16} />
              {profileLoading
                ? t('account.saving', 'Wird gspeichert…')
                : t('account.saveProfile', 'Profil speichere')}
            </Button>
          </div>
        </div>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <IconMail size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
          <Text fw={700} fz="md">
            {t('account.mail', 'Mail-Iistellige')}
          </Text>
        </Group>
        <div
          style={{
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          {emailVerified === false && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                padding: '12px 16px',
                background: 'var(--mantine-color-acc-0)',
                border: '1px solid #fece2b88',
                borderRadius: 8,
              }}
            >
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--mantine-color-acc-8)',
                }}
              >
                {t(
                  'account.verifyEmailToEnableForwarding',
                  'Verifizier dini private E-Mail zum Witergleiti aktiviere',
                )}
              </div>
              <Button
                size="sm"
                variant="default"
                onClick={sendVerificationEmail}
                disabled={verifyLoading}
              >
                {verifyLoading
                  ? t('account.sending', 'Wird gsendet…')
                  : t(
                      'account.sendVerificationEmail',
                      'Verifikations-E-Mail sende',
                    )}
              </Button>
            </div>
          )}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 500,
                  color:
                    emailVerified === false
                      ? 'var(--mantine-color-ink-3)'
                      : 'var(--mantine-color-ink-8)',
                }}
              >
                {t(
                  'account.forwardToPrivateEmail',
                  'A private E-Mail witergleite',
                )}
              </div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--mantine-color-ink-4)',
                  marginTop: 2,
                }}
              >
                {emailVerified === false
                  ? t(
                      'account.verifyEmailAboveToEnable',
                      '(E-Mail oben verifiziere zum aktiviere)',
                    )
                  : t(
                      'account.copyIncomingClubMail',
                      'Igangendi Club-Mail a dini private E-Mail-Adresse chopie',
                    )}
              </div>
            </div>
            <Toggle
              checked={mailForwarding}
              onChange={toggleMailForwarding}
              disabled={emailVerified === false}
            />
          </div>
          {mailSettingsQuery.isLoading && (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: 'var(--mantine-color-ink-3)',
              }}
            >
              {t(
                'account.loadingMailSettings',
                'Mail-Iistellige werden glade…',
              )}
            </div>
          )}
        </div>
      </Paper>
    </>
  )
}
