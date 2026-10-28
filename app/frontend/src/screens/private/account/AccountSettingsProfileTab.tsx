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
import { useT, zmsg } from '@/locales/i18n'

const profileSchema = z.object({
  displayName: z.string().min(1, zmsg('validation.displayNameRequired', 'Anzeigename ist erforderlich')),
  email: z.string().email(zmsg('validation.invalidEmail', 'Ungültige E-Mail-Adresse')),
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
      avatarColor: currentUser?.avatarColor ?? '#7441e0',
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
        t('account.profile.saved', 'Profil gespeichert'),
        t('account.profile.updatedMsg', 'Dein Profil wurde gespeichert.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('account.saveFailed', 'Speichern fehlgeschlagen'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotUpdateProfile',
              'Profil konnte nicht gespeichert werden.',
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
        t('account.mail.saved', 'Mail-Einstellungen gespeichert'),
        val
          ? t('account.forwardingEnabled', 'Weiterleitung eingeschaltet.')
          : t('account.forwardingDisabled', 'Weiterleitung ausgeschaltet.'),
      )
    } catch {
      setMailForwarding(!val)
      notify(
        'error',
        t('common.error', 'Fehler'),
        t(
          'account.couldNotUpdateMailSettings',
          'Mail-Einstellungen konnten nicht gespeichert werden.',
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
        t('account.verificationEmailSent', 'Bestätigungs-E-Mail gesendet'),
        t('account.checkInbox', 'Schau in dein privates E-Mail-Postfach.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotSendVerification',
              'Bestätigungs-E-Mail konnte nicht gesendet werden.',
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
            {t('account.profileLabel', 'Profil')}
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
                {t('account.avatarColor', 'Avatarfarbe')}
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
                  border: '1px solid #d6d2e3',
                }}
              />
            </div>
          </div>
          <Field label={t('common.displayName', 'Anzeigename')}>
            <TextInput {...profileForm.getInputProps('displayName')} />
          </Field>
          <Field
            label={t('account.privateEmail', 'Private E-Mail')}
            hint={t(
              'account.privateEmailHint',
              'Deine persönliche Adresse. Andere Mitglieder sehen sie nicht.',
            )}
          >
            <TextInput type="email" {...profileForm.getInputProps('email')} />
          </Field>
          <Field
            label={t('account.clubEmail', 'Vereins-E-Mail')}
            hint={t(
              'account.clubEmailHint',
              'Wird automatisch erstellt. Nur der Vorstand kann sie ändern.',
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
                {t('account.readOnly', 'nur lesen')}
              </span>
            </div>
          </Field>
          <Field
            label={t('account.profile.note', 'Profilnotiz')}
            hint={t(
              'account.profile.noteHint',
              'Ein kurzer Text über dich, den andere Mitglieder sehen.',
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
                ? t('account.saving', 'Wird gespeichert …')
                : t('account.saveProfile', 'Profil speichern')}
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
            {t('account.mailLabel', 'Mail-Einstellungen')}
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
                border: '1px solid #7441e088',
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
                  'Bestätige deine E-Mail-Adresse, um die Weiterleitung einzuschalten.',
                )}
              </div>
              <Button
                size="sm"
                variant="default"
                onClick={sendVerificationEmail}
                disabled={verifyLoading}
              >
                {verifyLoading
                  ? t('account.sending', 'Wird gesendet …')
                  : t(
                      'account.sendVerificationEmail',
                      'Bestätigungs-E-Mail senden',
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
                  'An private E-Mail weiterleiten',
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
                      '(Bestätige zuerst oben deine E-Mail-Adresse)',
                    )
                  : t(
                      'account.copyIncomingClubMail',
                      'Eingehende Vereins-Mails an meine private E-Mail kopieren',
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
                'Mail-Einstellungen werden geladen …',
              )}
            </div>
          )}
        </div>
      </Paper>
    </>
  )
}
