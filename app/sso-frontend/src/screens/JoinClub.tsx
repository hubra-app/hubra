import { useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Center,
  Loader,
  Paper,
  Radio,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { IconArrowLeft, IconCheck } from '@tabler/icons-react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import { clubAppUrl } from '@/redirect'
import * as authApi from '@/api/auth'
import { useLang } from '@/lang'

/**
 * A club's join page: what the club app's /apply sends people to. Signed in
 * (with a verified address), you ask to join and may pick a membership tier;
 * the club's admins approve it under Mitglieder → Anträge.
 */
export function JoinClubScreen() {
  const { slug = '' } = useParams()
  const { authStatus, urls, notify } = useSso()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [tierChoice, setTierChoice] = useState<string | null>(null)
  const { tr } = useLang()

  useEffect(() => {
    if (authStatus === 'anon')
      navigate(`/login?redirect=${encodeURIComponent(window.location.href)}`, { replace: true })
  }, [authStatus, navigate])

  const authed = authStatus === 'authed'
  const club = useQuery({
    queryKey: ['club', slug],
    queryFn: () => authApi.getClub(slug),
    enabled: authed && !!slug,
    retry: false,
  })

  const join = useMutation({
    mutationFn: (tierId?: number) => authApi.joinClub(slug, tierId),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['club', slug] })
      queryClient.invalidateQueries({ queryKey: ['my-tenants'] })
      queryClient.invalidateQueries({ queryKey: ['join-requests'] })
      notify(
        'success',
        res.status === 'joined'
          ? tr(`Du bist jetzt bei ${res.club.name}`, `You're now in ${res.club.name}`)
          : tr('Anfrage gesendet', 'Request sent'),
      )
    },
    onError: (err: Error) =>
      notify('error', tr('Anfrage fehlgeschlagen', 'Request failed'), err.message),
  })

  const openClub = async () => {
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
        tr('Der Verein konnte nicht geöffnet werden', 'The club could not be opened'),
        err instanceof Error ? err.message : undefined,
      )
    }
  }

  if (!authed || club.isLoading)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  const back = (
    <Button
      variant="subtle"
      size="xs"
      leftSection={<IconArrowLeft size={16} />}
      onClick={() => navigate('/clubs')}
    >
      {tr('Meine Vereine', 'My clubs')}
    </Button>
  )

  if (club.isError || !club.data)
    return (
      <SignedInFrame actions={back}>
        <Alert color="red" title={tr('Verein nicht gefunden', 'Club not found')}>
          {tr(
            'Diesen Verein gibt es nicht oder er ist nicht aktiv. Suche ihn unter «Meine Vereine».',
            "This club doesn't exist or isn't active. Look for it under “My clubs”.",
          )}
        </Alert>
      </SignedInFrame>
    )

  const data = club.data
  const tiers = data.tiers
  const tierId = tierChoice ?? (tiers[0] ? String(tiers[0].id) : null)

  return (
    <SignedInFrame actions={back}>
      <Paper withBorder radius="md" p="xl">
        <Stack gap="md">
          <div>
            <Text size="sm" c="dimmed">
              {tr('Verein', 'Club')}
            </Text>
            <Title order={2}>{data.name}</Title>
          </div>

          {data.membership === 'member' && (
            <>
              <Badge color="green" leftSection={<IconCheck size={12} />} w="fit-content">
                {tr('Du bist Mitglied', "You're a member")}
              </Badge>
              <Button onClick={openClub}>{tr('Verein öffnen', 'Open club')}</Button>
            </>
          )}

          {data.membership === 'pending' && (
            <Alert
              color="yellow"
              title={tr('Deine Anfrage ist unterwegs', 'Your request is on its way')}
            >
              {tr(
                `${data.name} prüft sie. Sobald sie angenommen ist, findest du den Verein unter «Meine Vereine».`,
                `${data.name} is reviewing it. Once it's accepted, you'll find the club under “My clubs”.`,
              )}
            </Alert>
          )}

          {data.membership === null && !data.canJoinDirectly && data.acceptsRequests === false && (
            <Alert color="gray" title={tr('Nur auf Einladung', 'Invitation only')}>
              {tr(
                `${data.name} nimmt neue Mitglieder nur auf Einladung auf. Wenn du dabei sein möchtest, frag jemanden aus dem Verein nach einer Einladung.`,
                `${data.name} only takes new members by invitation. If you'd like to join, ask someone in the club for an invitation.`,
              )}
            </Alert>
          )}

          {data.membership === null && (data.canJoinDirectly || data.acceptsRequests !== false) && (
            <>
              <Text size="sm">
                {data.canJoinDirectly
                  ? tr(
                      'Als Plattform-Verwaltung trittst du direkt bei.',
                      'As a platform admin you join directly.',
                    )
                  : tr(
                      'Schick dem Verein eine Beitrittsanfrage. Seine Verwaltung nimmt sie an oder lehnt sie ab; Name und E-Mail-Adresse aus deinem Konto gehen mit.',
                      "Send the club a request to join. Its admins accept or decline it; your account's name and email address go with it.",
                    )}
              </Text>
              {tiers.length > 0 && !data.canJoinDirectly && (
                <Radio.Group
                  label={tr('Mitgliedschaft', 'Membership')}
                  value={tierId}
                  onChange={setTierChoice}
                >
                  <Stack gap={6} mt={6}>
                    {tiers.map((t) => (
                      <Radio key={t.id} value={String(t.id)} label={t.name} />
                    ))}
                  </Stack>
                </Radio.Group>
              )}
              <Button
                loading={join.isPending}
                onClick={() =>
                  join.mutate(tierId && !data.canJoinDirectly ? Number(tierId) : undefined)
                }
              >
                {data.canJoinDirectly
                  ? tr('Beitreten', 'Join')
                  : tr('Beitritt anfragen', 'Ask to join')}
              </Button>
            </>
          )}
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}
