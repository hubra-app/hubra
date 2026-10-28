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
      notify(
        'success',
        res.status === 'joined' ? `Du bist jetzt bei ${res.club.name}` : 'Anfrage gesendet',
      )
    },
    onError: (err: Error) => notify('error', 'Anfrage fehlgeschlagen', err.message),
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
      notify('error', 'Der Verein konnte nicht geöffnet werden', err instanceof Error ? err.message : undefined)
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
      Meine Vereine
    </Button>
  )

  if (club.isError || !club.data)
    return (
      <SignedInFrame actions={back}>
        <Alert color="red" title="Verein nicht gefunden">
          Diesen Verein gibt es nicht oder er ist nicht aktiv. Suche ihn unter «Meine Vereine».
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
              Verein
            </Text>
            <Title order={2}>{data.name}</Title>
          </div>

          {data.membership === 'member' && (
            <>
              <Badge color="green" leftSection={<IconCheck size={12} />} w="fit-content">
                Du bist Mitglied
              </Badge>
              <Button onClick={openClub}>Verein öffnen</Button>
            </>
          )}

          {data.membership === 'pending' && (
            <Alert color="yellow" title="Deine Anfrage ist unterwegs">
              {data.name} prüft sie. Sobald sie angenommen ist, findest du den Verein unter «Meine
              Vereine».
            </Alert>
          )}

          {data.membership === null && (
            <>
              <Text size="sm">
                {data.canJoinDirectly
                  ? 'Als Plattform-Verwaltung trittst du direkt bei.'
                  : 'Schick dem Verein eine Beitrittsanfrage. Seine Verwaltung nimmt sie an oder lehnt sie ab; Name und E-Mail-Adresse aus deinem Konto gehen mit.'}
              </Text>
              {tiers.length > 0 && !data.canJoinDirectly && (
                <Radio.Group
                  label="Mitgliedschaft"
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
                onClick={() => join.mutate(tierId && !data.canJoinDirectly ? Number(tierId) : undefined)}
              >
                {data.canJoinDirectly ? 'Beitreten' : 'Beitritt anfragen'}
              </Button>
            </>
          )}
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}
