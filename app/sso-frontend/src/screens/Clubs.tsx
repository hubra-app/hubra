import { useEffect, useState } from 'react'
import {
  Alert,
  Avatar,
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { IconArrowRight, IconBuildingCommunity, IconPlus, IconSearch } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { clubAppUrl } from '@/redirect'
import * as authApi from '@/api/auth'
import { SignedInFrame } from '@/components/SignedInFrame'
import { LoadFailed } from '@/components/LoadFailed'
import { useLang } from '@/lang'

/**
 * The club picker: where everyone lands after signing in. Lists their clubs
 * (and the manager portal for platform managers), and lets them find another
 * club and ask to join it (platform managers join straight away).
 */
export function ClubsScreen() {
  const { authStatus, isManager, urls, notify } = useSso()
  const navigate = useNavigate()
  const { tr } = useLang()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [debounced] = useDebouncedValue(search.trim(), 250)
  const [opening, setOpening] = useState<string | null>(null)

  useEffect(() => {
    if (authStatus === 'anon') navigate('/login', { replace: true })
  }, [authStatus, navigate])

  const authed = authStatus === 'authed'
  const mine = useQuery({
    queryKey: ['my-tenants'],
    queryFn: authApi.getMyTenants,
    enabled: authed,
  })
  const waiting = useQuery({
    queryKey: ['join-requests'],
    queryFn: authApi.getMyJoinRequests,
    enabled: authed,
  })
  const found = useQuery({
    queryKey: ['clubs', debounced],
    queryFn: () => authApi.findClubs(debounced),
    enabled: authed && (debounced.length >= 2 || isManager),
  })

  const join = useMutation({
    mutationFn: (slug: string) => authApi.joinClub(slug),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['clubs'] })
      queryClient.invalidateQueries({ queryKey: ['my-tenants'] })
      queryClient.invalidateQueries({ queryKey: ['join-requests'] })
      if (res.status === 'joined') {
        notify('success', tr(`Du bist jetzt bei ${res.club.name}`, `You joined ${res.club.name}`))
      } else {
        notify(
          'success',
          tr('Anfrage gesendet', 'Request sent'),
          tr(
            `${res.club.name} prüft deine Anfrage. Sobald sie angenommen ist, kannst du den Verein öffnen.`,
            `${res.club.name} will review it. You can open the club once they accept.`,
          ),
        )
      }
    },
    onError: (err: Error) => notify('error', tr('Beitreten fehlgeschlagen', 'Could not join'), err.message),
  })

  const openClub = async (slug: string) => {
    setOpening(slug)
    try {
      await authApi.switchTenant(slug)
      window.location.assign(clubAppUrl(urls, slug))
    } catch (err: unknown) {
      setOpening(null)
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

  if (!authed)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  const myClubs = mine.data?.tenants ?? []
  // Club owners and admins run their club in the manager portal too.
  const runsAClub = myClubs.some((t) => t.admin_level)
  const pending = waiting.data?.requests ?? []
  const results = found.data?.clubs ?? []
  const canJoinDirectly = found.data?.canJoinDirectly ?? false

  return (
    <SignedInFrame width={640}>
      <Group justify="space-between" align="flex-end" mb="lg" gap="sm">
        <div>
          <Title order={1} fz={30} mb={6}>
            {tr('Meine Vereine', 'My clubs')}
          </Title>
          <Text c="dimmed">
            {tr('Wähle einen Verein oder tritt einem neuen bei.', 'Pick a club or join a new one.')}
          </Text>
        </div>
        <Button
          variant="default"
          leftSection={<IconPlus size={16} />}
          onClick={() => navigate('/start')}
        >
          {tr('Verein gründen', 'Start a club')}
        </Button>
      </Group>

      {(isManager || runsAClub) && (
        <Paper withBorder p="md" mb="lg" style={{ background: '#f5f1ff', borderColor: '#d6c7ff' }}>
          <Group justify="space-between" wrap="nowrap">
            <Box style={{ minWidth: 0 }}>
              <Text fw={700}>{tr('Verwaltung', 'Manager portal')}</Text>
              <Text fz="sm" c="dimmed">
                {isManager
                  ? tr(
                      'Vereine, Anfragen, Rollen und Plugins dieser Plattform',
                      'Clubs, requests, roles and plugins of this platform',
                    )
                  : tr('Admins und Einstellungen deiner Vereine', 'Admins and settings of the clubs you run')}
              </Text>
            </Box>
            <Button
              component="a"
              href={urls.manage}
              style={{ flexShrink: 0 }}
              rightSection={<IconArrowRight size={16} />}
            >
              {tr('Öffnen', 'Open')}
            </Button>
          </Group>
        </Paper>
      )}

      {mine.isLoading ? (
        <Loader size="sm" my="md" />
      ) : mine.isError ? (
        <LoadFailed onRetry={() => mine.refetch()} />
      ) : myClubs.length === 0 ? (
        <Paper withBorder p="xl" mb="xl">
          <Stack align="center" gap="xs" ta="center">
            <IconBuildingCommunity size={32} color="#7441e0" />
            <Text fw={700}>{tr('Noch kein Verein', 'No club yet')}</Text>
            <Text size="sm" c="dimmed" maw={380}>
              {tr(
                'Such deinen Verein unten und frag an, ob du beitreten darfst.',
                'Find your club below and ask to join.',
              )}
            </Text>
          </Stack>
        </Paper>
      ) : (
        <Stack gap="sm" mb="xl">
          {myClubs.map((t) => (
            <Paper key={t.tenant_slug} withBorder p="md">
              <Group justify="space-between" wrap="nowrap">
                <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
                  <Avatar radius="md" size={44} color="acc" variant="light">
                    {(t.tenant_name ?? t.tenant_slug).slice(0, 2).toUpperCase()}
                  </Avatar>
                  <Box style={{ minWidth: 0 }}>
                    <Text fw={700} truncate>
                      {t.tenant_name}
                    </Text>
                    <Group gap={6} wrap="nowrap">
                      <Text fz="sm" c="dimmed" truncate>
                        {t.tenant_slug}
                      </Text>
                      {t.admin_level && (
                        <Badge size="xs" variant="light">
                          {t.admin_level === 'owner' ? tr('Inhaber', 'Owner') : 'Admin'}
                        </Badge>
                      )}
                    </Group>
                  </Box>
                </Group>
                <Button
                  variant="light"
                  style={{ flexShrink: 0 }}
                  rightSection={<IconArrowRight size={16} />}
                  loading={opening === t.tenant_slug}
                  onClick={() => openClub(t.tenant_slug)}
                >
                  {tr('Öffnen', 'Open')}
                </Button>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}

      {pending.length > 0 && (
        <>
          <Title order={2} fz={20} mb="sm">
            {tr('Wartet auf Freigabe', 'Waiting for approval')}
          </Title>
          <Stack gap="sm" mb="xl">
            {pending.map((c) => (
              <Paper key={c.slug} withBorder p="md">
                <Group justify="space-between" wrap="nowrap">
                  <Box style={{ minWidth: 0 }}>
                    <Text fw={700} truncate>
                      {c.name}
                    </Text>
                    <Text fz="sm" c="dimmed">
                      {tr(
                        'Der Verein prüft deine Anfrage. Danach kannst du ihn hier öffnen.',
                        'The club is reviewing your request. Once accepted you can open it here.',
                      )}
                    </Text>
                  </Box>
                  <Badge variant="light" color="gray" style={{ flexShrink: 0 }}>
                    {tr('Anfrage gesendet', 'Request sent')}
                  </Badge>
                </Group>
              </Paper>
            ))}
          </Stack>
        </>
      )}

      <Title order={2} fz={20} mb="sm">
        {tr('Verein finden', 'Find a club')}
      </Title>
      <TextInput
        size="md"
        placeholder={tr('Name des Vereins', 'Club name')}
        leftSection={<IconSearch size={18} />}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        mb="md"
        aria-label={tr('Vereine suchen', 'Search clubs')}
      />

      {found.isFetching && <Loader size="sm" />}
      {found.isError && (
        <Alert color="red" variant="light">
          {(found.error as Error).message}
        </Alert>
      )}
      {!found.isFetching && debounced.length >= 2 && results.length === 0 && (
        <Text size="sm" c="dimmed">
          {tr(`Kein Verein passt zu «${debounced}».`, `No club matches “${debounced}”.`)}
        </Text>
      )}
      <Stack gap="sm">
        {results.map((c) => (
          <Paper key={c.slug} withBorder p="md">
            <Group justify="space-between" wrap="nowrap">
              <Box style={{ minWidth: 0 }}>
                <Text fw={700} truncate>
                  {c.name}
                </Text>
                <Text fz="sm" c="dimmed">
                  {c.slug}
                </Text>
              </Box>
              {c.membership === 'member' ? (
                <Button
                  variant="light"
                  style={{ flexShrink: 0 }}
                  loading={opening === c.slug}
                  onClick={() => openClub(c.slug)}
                >
                  {tr('Öffnen', 'Open')}
                </Button>
              ) : c.membership === 'pending' ? (
                <Badge variant="light" color="gray" style={{ flexShrink: 0 }}>
                  {tr('Anfrage gesendet', 'Request sent')}
                </Badge>
              ) : (
                <Button
                  style={{ flexShrink: 0 }}
                  loading={join.isPending && join.variables === c.slug}
                  onClick={() => join.mutate(c.slug)}
                >
                  {canJoinDirectly ? tr('Beitreten', 'Join') : tr('Beitritt anfragen', 'Ask to join')}
                </Button>
              )}
            </Group>
          </Paper>
        ))}
      </Stack>
    </SignedInFrame>
  )
}
