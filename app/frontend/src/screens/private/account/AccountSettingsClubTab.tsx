import { useState } from 'react'
import { Anchor, Button, Group, Paper, Text, TextInput } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconExternalLink, IconMail, IconUser } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useAuth, useToast } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { Avatar, Field, Toggle } from '@/components/ui'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'

/**
 * What the account looks like in this club. Name, email, password,
 * language and sessions belong to the account on the SSO portal; here is
 * only what this club adds: its mail address and forwarding.
 */
export function AccountSettingsClubTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser } = useAuth()
  const { ssoUrl } = useInstance()
  // The switch shows the saved value until the person flips it.
  const [forwardingChoice, setMailForwarding] = useState<boolean | null>(null)

  const accountQuery = useQuery({
    queryKey: qk.account.all,
    queryFn: () => authApi.getAccount(),
  })
  const mailSettingsQuery = useQuery({
    queryKey: qk.account.mailSettings,
    queryFn: () => authApi.getMailSettings(),
  })
  const emailVerified = mailSettingsQuery.data?.private_email_verified ?? null
  const clubEmail = accountQuery.data?.publicEmail ?? ''

  const mailForwarding = forwardingChoice ?? mailSettingsQuery.data?.forwarding_enabled ?? false

  const toggleMailForwarding = async (val: boolean) => {
    setMailForwarding(val)
    try {
      await authApi.updateMailSettings(val)
      notify(
        'success',
        t('account.mail.saved', 'Mail-Einstellungen gespeichert'),
        val
          ? t('account.club.forwardingOn', 'Weiterleitung eingeschaltet.')
          : t('account.club.forwardingOff', 'Weiterleitung ausgeschaltet.'),
      )
    } catch {
      setMailForwarding(!val)
      notify(
        'error',
        t('common.error', 'Fehler'),
        t('account.club.forwardingFailed', 'Die Weiterleitung konnte nicht geändert werden.'),
      )
    }
  }

  return (
    <>
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Group justify="space-between" wrap="nowrap" gap="md">
          <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
            <Avatar
              name={currentUser?.name ?? ''}
              color={currentUser?.avatarColor ?? '#7441e0'}
              size={44}
            />
            <div style={{ minWidth: 0 }}>
              <Text fw={700} truncate>
                {currentUser?.name}
              </Text>
              <Text size="sm" c="dimmed" truncate>
                {currentUser?.email}
              </Text>
            </div>
          </Group>
          <Button
            component="a"
            href={`${ssoUrl}/account`}
            variant="light"
            leftSection={<IconUser size={16} />}
            rightSection={<IconExternalLink size={14} />}
            style={{ flexShrink: 0 }}
          >
            {t('account.club.manageAccount', 'Konto verwalten')}
          </Button>
        </Group>
        <Text size="sm" c="dimmed" mt="md">
          {t(
            'account.club.accountHint',
            'Name, E-Mail, Passwort, Sprache und Sitzungen gelten für alle deine Vereine und werden in deinem Hubra-Konto geändert.',
          )}
        </Text>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg">
        <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
          <IconMail size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
          <Text fw={700} fz="md">
            {t('account.club.mailTitle', 'Vereins-Mail')}
          </Text>
        </Group>
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field
            label={t('account.clubEmail', 'Vereinsadresse')}
            hint={t(
              'account.club.addressHint',
              'Vom Verein vergeben. Für eine Änderung wende dich an die Vereinsleitung.',
            )}
          >
            <TextInput
              value={clubEmail}
              readOnly
              aria-label={t('account.clubEmail', 'Vereinsadresse')}
              styles={{
                input: { fontFamily: '"JetBrains Mono"', fontSize: 'var(--mantine-font-size-sm)' },
              }}
            />
          </Field>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <div>
              <Text size="sm" fw={500}>
                {t('account.club.forward', 'An meine private Adresse weiterleiten')}
              </Text>
              <Text size="xs" c="dimmed" mt={2}>
                {emailVerified === false ? (
                  <>
                    {t('account.club.verifyFirst', 'Bestätige zuerst deine private Adresse.')}{' '}
                    <Anchor href={`${ssoUrl}/account/email`} size="xs">
                      {t('account.club.verifyNow', 'Jetzt bestätigen')}
                    </Anchor>
                  </>
                ) : (
                  t(
                    'account.club.forwardHint',
                    'Eingehende Vereins-Mails gehen als Kopie an deine private Adresse.',
                  )
                )}
              </Text>
            </div>
            <Toggle
              checked={mailForwarding}
              label={t('account.club.forward', 'An meine private Adresse weiterleiten')}
              onChange={toggleMailForwarding}
              disabled={emailVerified !== true}
            />
          </div>
        </div>
      </Paper>
    </>
  )
}
