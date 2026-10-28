import { useEffect, useState } from 'react'
import { Alert, Button, Center, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearTokens } from '@hubra/api-client'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { AuthFrame } from '@/components/AuthFrame'
import { SignedInFrame } from '@/components/SignedInFrame'
import { clubAppUrl } from '@/redirect'
import { useLang } from '@/lang'
import * as authApi from '@/api/auth'

/** The token from the link (`/invite#token=…`); the hash never reaches a server log. */
function inviteToken(): string {
  return new URLSearchParams(window.location.hash.slice(1)).get('token') ?? ''
}

/**
 * A club's personal invite link. The person signs in, or signs up with the
 * invited address, and accepts here; that makes them a member. The club
 * never creates or changes the account itself.
 */
export function InviteScreen() {
  const { authStatus, urls, notify } = useSso()
  const { tr } = useLang()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [token] = useState(inviteToken)
  const authed = authStatus === 'authed'
  const here = encodeURIComponent(window.location.href)

  const invite = useQuery({
    queryKey: ['invite', token],
    queryFn: () => authApi.lookupInvite(token),
    enabled: authed && !!token,
    retry: false,
  })

  const openClub = async (slug: string) => {
    try {
      await authApi.switchTenant(slug)
      window.location.assign(clubAppUrl(urls, slug))
    } catch (err: unknown) {
      if ((err as { code?: string }).code === 'EMAIL_NOT_VERIFIED') {
        navigate('/verify')
        return
      }
      notify(
        'error',
        tr('Der Verein konnte nicht geöffnet werden', 'Could not open the club'),
        err instanceof Error ? err.message : undefined,
      )
    }
  }

  const accept = useMutation({
    mutationFn: () => authApi.acceptInvite(token),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['my-tenants'] })
      notify('success', tr(`Du bist jetzt bei ${res.club.name}`, `You joined ${res.club.name}`))
      openClub(res.club.slug)
    },
    onError: (err: Error) => notify('error', tr('Annehmen fehlgeschlagen', 'Could not accept'), err.message),
  })

  useEffect(() => {
    if (invite.data?.membership === 'member') queryClient.invalidateQueries({ queryKey: ['my-tenants'] })
  }, [invite.data, queryClient])

  if (authStatus === 'loading' || (authed && invite.isLoading))
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  if (!authed)
    return (
      <AuthFrame>
        <Title order={1} fz={30} mb={6}>
          {tr('Du bist eingeladen', "You're invited")}
        </Title>
        <Text c="dimmed" mb={28}>
          {tr(
            'Melde dich mit der E-Mail-Adresse an, an die die Einladung ging, oder erstelle damit ein Konto. Danach nimmst du die Einladung an.',
            'Sign in with the email address the invite was sent to, or create an account with it. Then accept the invite.',
          )}
        </Text>
        <Stack gap="sm">
          <Button size="md" fullWidth onClick={() => navigate(`/login?redirect=${here}`)}>
            {tr('Anmelden', 'Sign in')}
          </Button>
          <Button variant="default" size="md" fullWidth onClick={() => navigate(`/signup?redirect=${here}`)}>
            {tr('Konto erstellen', 'Create account')}
          </Button>
        </Stack>
      </AuthFrame>
    )

  if (!token || invite.isError || !invite.data)
    return (
      <SignedInFrame>
        <Alert color="red" title={tr('Einladung ungültig', 'Invite not valid')}>
          {tr(
            'Dieser Link ist abgelaufen, wurde schon benutzt oder durch eine neuere Einladung ersetzt. Bitte den Verein um eine neue.',
            'This link has expired, was already used or was replaced by a newer invite. Ask the club for a new one.',
          )}
        </Alert>
      </SignedInFrame>
    )

  const data = invite.data
  return (
    <SignedInFrame>
      <Paper withBorder radius="md" p="xl">
        <Stack gap="md">
          <div>
            <Text size="sm" c="dimmed">
              {tr('Einladung', 'Invite')}
            </Text>
            <Title order={2}>{data.club.name}</Title>
          </div>

          {data.membership === 'member' ? (
            <>
              <Text size="sm">{tr('Du bist schon Mitglied.', "You're already a member.")}</Text>
              <Button onClick={() => openClub(data.club.slug)}>{tr('Verein öffnen', 'Open club')}</Button>
            </>
          ) : data.emailMatches ? (
            <>
              <Text size="sm">
                {tr(
                  `${data.invitedBy} lädt dich ein, Mitglied zu werden. Mit dem Annehmen sieht der Verein Name, E-Mail und Kontaktangaben aus deinem Konto; ändern kannst nur du sie.`,
                  `${data.invitedBy} invites you to become a member. When you accept, the club sees the name, email and contact details of your account; only you can change them.`,
                )}
              </Text>
              <Group>
                <Button loading={accept.isPending} onClick={() => accept.mutate()}>
                  {tr('Einladung annehmen', 'Accept invite')}
                </Button>
              </Group>
            </>
          ) : (
            <>
              <Alert color="yellow" title={tr('Anderes Konto', 'Different account')}>
                {tr(
                  `Die Einladung ging an ${data.email}. Melde dich mit diesem Konto an, oder erstelle eines mit dieser Adresse.`,
                  `The invite was sent to ${data.email}. Sign in with that account, or create one with this address.`,
                )}
              </Alert>
              <Button
                variant="default"
                onClick={async () => {
                  await authApi.logout()
                  clearTokens()
                  window.location.assign(`/login?redirect=${here}`)
                }}
              >
                {tr('Abmelden und wechseln', 'Sign out and switch')}
              </Button>
            </>
          )}
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}
