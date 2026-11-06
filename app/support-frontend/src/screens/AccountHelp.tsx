import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Button, Group, List, Paper, Stack, Text, ThemeIcon } from '@mantine/core'
import { IconBellOff, IconBug, IconShieldLock } from '@tabler/icons-react'
import type { ReactNode } from 'react'
import { SSO_URL } from '@hubra/api-client'
import { Page } from '@/components/Layout'
import { useAuth } from '@/auth'
import { myClubs } from '@/api/support'
import { ACCOUNT_URL, APP_URL } from '@/urls'
import { useLang } from '@/lang'

/**
 * /konto: the self-service answers people look for after a mail: "that
 * sign-in wasn't me", "stop sending me this", and "something is broken".
 * Every action itself lives where it already is (SSO account, club app,
 * report form); this page only leads there. Mails link here from their
 * footer when the platform setting support.url is set.
 */
export function AccountHelpScreen() {
  const { tr } = useLang()
  const { hash } = useLocation()
  // /nicht-ich and /abmelden land on their card.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [hash])
  return (
    <Page
      narrow
      title={tr('Konto und Mails', 'Account and mails')}
      intro={tr(
        'Eine Anmeldung, die du nicht kennst? Zu viele Mails? Etwas funktioniert nicht? Hier findest du den schnellsten Weg.',
        "A sign-in you don't recognise? Too many mails? Something not working? Here is the quickest way.",
      )}
    >
      <Stack gap="lg">
        <NotMeCard />
        <MailsCard />
        <ReportCard />
      </Stack>
    </Page>
  )
}

function Card({
  id,
  icon,
  color,
  title,
  children,
}: {
  id: string
  icon: ReactNode
  color: string
  title: string
  children: ReactNode
}) {
  return (
    <Paper withBorder p="lg" radius="lg" id={id} data-testid={`konto-${id}`}>
      <Group gap="sm" mb="sm" wrap="nowrap">
        <ThemeIcon size={40} radius="md" variant="light" color={color}>
          {icon}
        </ThemeIcon>
        <Text fw={700} fz="lg">
          {title}
        </Text>
      </Group>
      <Stack gap="sm">{children}</Stack>
    </Paper>
  )
}

function NotMeCard() {
  const { tr } = useLang()
  const { status } = useAuth()
  return (
    <Card
      id="nicht-ich"
      icon={<IconShieldLock size={22} />}
      color="red"
      title={tr('Das warst nicht du?', "That wasn't you?")}
    >
      <Text size="sm" c="dimmed">
        {tr(
          'Du hast eine Mail über eine neue Anmeldung bekommen, die du nicht kennst, oder glaubst, jemand anderes nutzt dein Konto? Dann:',
          "You got a mail about a new sign-in you don't recognise, or think someone else uses your account? Then:",
        )}
      </Text>
      <List size="sm" spacing={4} type="ordered">
        <List.Item>
          {tr(
            'Tippe in der Mail auf «Das war ich nicht». Das beendet sofort jede Anmeldung, auf allen Geräten.',
            'Tap "That wasn\'t me" in the mail. It ends every sign-in at once, on every device.',
          )}
        </List.Item>
        <List.Item>
          {tr('Setze ein neues Passwort.', 'Set a new password.')}
        </List.Item>
        <List.Item>
          {tr(
            'Schalte die Zwei-Faktor-Anmeldung ein, falls sie noch aus ist.',
            'Turn on two-factor sign-in if it is still off.',
          )}
        </List.Item>
      </List>
      <Group gap="sm">
        {status === 'authed' ? (
          <>
            <Button component="a" href={`${ACCOUNT_URL}/sitzungen`} color="red">
              {tr('Anmeldungen beenden', 'End sign-ins')}
            </Button>
            <Button component="a" href={`${ACCOUNT_URL}/passwort`} variant="default">
              {tr('Passwort ändern', 'Change password')}
            </Button>
            <Button component="a" href={`${ACCOUNT_URL}/zwei-faktor`} variant="default">
              {tr('Zwei-Faktor', 'Two-factor')}
            </Button>
          </>
        ) : (
          <Button component="a" href={`${SSO_URL}/forgot-password`} color="red">
            {tr('Neues Passwort setzen', 'Set a new password')}
          </Button>
        )}
      </Group>
      <Text size="sm" c="dimmed">
        {tr('Du kommst nicht mehr in dein Konto?', "You can't get into your account any more?")}{' '}
        <Anchor component={Link} to="/kontakt?area=account" size="sm">
          {tr('Schreib uns', 'Write to us')}
        </Anchor>
        .
      </Text>
    </Card>
  )
}

function MailsCard() {
  const { tr } = useLang()
  const { status } = useAuth()
  const clubs = useQuery({ queryKey: ['my-clubs'], queryFn: myClubs, enabled: status === 'authed' })
  return (
    <Card
      id="mails"
      icon={<IconBellOff size={22} />}
      color="orange"
      title={tr('Mails und Benachrichtigungen abbestellen', 'Unsubscribe from mails and notifications')}
    >
      <Text size="sm" c="dimmed">
        {tr(
          'Mails von Hubra selbst (neue Geräte, Antworten auf deine Meldungen) stellst du in deinem Konto ein. Was ein Verein dir schickt (Anlässe, Umfragen, Wochenübersicht), stellst du im jeweiligen Verein ein. Mails, die du brauchst (Passwort, Rechnungen, Einladungen), kommen immer.',
          'Mails from Hubra itself (new devices, answers to your reports) are set in your account. What a club sends you (events, polls, weekly digest) is set in that club. Mails you need (password, invoices, invites) always come.',
        )}
      </Text>
      <Group gap="sm">
        <Button component="a" href={`${ACCOUNT_URL}/benachrichtigungen`}>
          {tr('Hubra-Benachrichtigungen', 'Hubra notifications')}
        </Button>
      </Group>
      {status === 'authed' && (clubs.data ?? []).length > 0 && (
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            {tr('Deine Vereine', 'Your clubs')}
          </Text>
          {(clubs.data ?? []).map((c) => (
            <Anchor
              key={c.tenant_slug}
              href={`${APP_URL}/${c.tenant_slug}/app/account/settings`}
              size="sm"
            >
              {tr(`Benachrichtigungen bei ${c.tenant_name}`, `Notifications at ${c.tenant_name}`)}
            </Anchor>
          ))}
        </Stack>
      )}
      {status !== 'authed' && (
        <Text size="sm" c="dimmed">
          {tr(
            'Melde dich an, dann zeigen wir hier deine Vereine mit dem direkten Link.',
            'Sign in and we show your clubs here with a direct link.',
          )}
        </Text>
      )}
    </Card>
  )
}

function ReportCard() {
  const { tr } = useLang()
  return (
    <Card id="problem" icon={<IconBug size={22} />} color="grape" title={tr('Problem melden', 'Report a problem')}>
      <Text size="sm" c="dimmed">
        {tr(
          'Ein Link führt ins Leere, eine Seite zeigt einen Fehler, eine Mail stimmt nicht? Sag uns, was passiert ist. Wir antworten per Mail und unter «Meine Meldungen».',
          "A link leads nowhere, a page shows an error, a mail is wrong? Tell us what happened. We answer by mail and under \"My reports\".",
        )}
      </Text>
      <Group gap="sm">
        <Button component={Link} to="/melden">
          {tr('Problem melden', 'Report a problem')}
        </Button>
        <Button component={Link} to="/meine" variant="default">
          {tr('Meine Meldungen', 'My reports')}
        </Button>
      </Group>
    </Card>
  )
}
