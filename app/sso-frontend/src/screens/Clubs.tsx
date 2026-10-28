import { useEffect, useState } from 'react'
import {
  Alert,
  Anchor,
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
import { IconArrowRight, IconSearch, IconUserCircle } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { clubAppUrl } from '@/redirect'
import * as authApi from '@/api/auth'
import { SignedInFrame } from '@/components/SignedInFrame'
import { tr, useLang } from '@/lang'

/**
 * The club picker: where everyone lands after signing in. Lists their clubs
 * (and the manager portal for platform managers), and lets them find another
 * club and ask to join it (platform managers join straight away).
 */
export function ClubsScreen() {
  useLang()
  const { authStatus, isManager, urls, notify } = useSso()
  const navigate = useNavigate()
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
  const found = useQuery({
    queryKey: ['clubs', debounced],
    queryFn: () => authApi.findClubs(debounced),
    enabled: authed && (debounced.length >= 2 || isManager),
  })

  const join = useMutation({
    mutationFn: authApi.joinClub,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['clubs'] })
      queryClient.invalidateQueries({ queryKey: ['my-tenants'] })
      if (res.status === 'joined') {
        notify('success', tr(`Du bist ${res.club.name} beigetreten`, `You joined ${res.club.name}`))
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
    onError: (err: Error) => notify('error', tr('Beitritt nicht möglich', 'Could not join'), err.message),
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
        tr('Verein lässt sich nicht öffnen', 'Could not open the club'),
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
  const results = found.data?.clubs ?? []
  const canJoinDirectly = found.data?.canJoinDirectly ?? false

  return (
    <SignedInFrame
      actions={
        <Button
          variant="subtle"
          size="xs"
          leftSection={<IconUserCircle size={16} />}
          onClick={() => navigate('/account')}
        >
          {tr('Mein Konto', 'My account')}
        </Button>
      }
    >

        {(isManager || runsAClub) && (
          <Paper withBorder radius="md" p="md" mb="xl">
            <Group justify="space-between" wrap="nowrap">
              <Box style={{ minWidth: 0 }}>
                <Text fw={600}>{tr('Verwaltung', 'Manager portal')}</Text>
                <Text fz="xs" c="dimmed">
                  {isManager
                    ? tr(
                        'Vereine, Anfragen, Rollen und Plugins der Plattform',
                        'Clubs, requests, roles and plugins of this platform',
                      )
                    : tr('Admins und Einstellungen deiner Vereine', 'Admins and settings of the clubs you run')}
                </Text>
              </Box>
              <Button
                component="a"
                href={urls.manage}
                variant="light"
                style={{ flexShrink: 0 }}
                rightSection={<IconArrowRight size={16} />}
              >
                {tr('Öffnen', 'Open')}
              </Button>
            </Group>
          </Paper>
        )}

        <Title order={2} mb={6}>
          {tr('Deine Vereine', 'Your clubs')}
        </Title>
        {mine.isLoading ? (
          <Loader size="sm" my="md" />
        ) : myClubs.length === 0 ? (
          <Text size="sm" c="dimmed" mb="xl">
            {tr(
              'Du bist noch in keinem Verein. Such deinen Verein unten und bitte um Aufnahme.',
              'You are not a member of a club yet. Find yours below and ask to join.',
            )}
          </Text>
        ) : (
          <Stack gap="sm" mb="xl" mt="md">
            {myClubs.map((t) => (
              <Paper key={t.tenant_slug} withBorder radius="md" p="md">
                <Group justify="space-between" wrap="nowrap">
                  <Box style={{ minWidth: 0 }}>
                    <Text fw={600} truncate>
                      {t.tenant_name}
                    </Text>
                    <Group gap={6} wrap="nowrap">
                      <Text fz="xs" c="dimmed">
                        {t.tenant_slug}
                      </Text>
                      {t.admin_level && (
                        <Badge size="xs" variant="light">
                          {t.admin_level === 'owner' ? tr('Inhaber', 'Owner') : 'Admin'}
                        </Badge>
                      )}
                    </Group>
                  </Box>
                  <Button
                    variant="light"
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

        <Title order={3} mb={6}>
          {tr('Verein finden', 'Find a club')}
        </Title>
        <TextInput
          placeholder={tr('Name des Vereins', 'Club name')}
          leftSection={<IconSearch size={16} />}
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
            <Paper key={c.slug} withBorder radius="md" p="md">
              <Group justify="space-between" wrap="nowrap">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={600} truncate>
                    {c.name}
                  </Text>
                  <Text fz="xs" c="dimmed">
                    {c.slug}
                  </Text>
                </Box>
                {c.membership === 'member' ? (
                  <Button
                    variant="light"
                    loading={opening === c.slug}
                    onClick={() => openClub(c.slug)}
                  >
                    {tr('Öffnen', 'Open')}
                  </Button>
                ) : c.membership === 'pending' ? (
                  <Badge variant="light" color="gray">
                    {tr('Anfrage gesendet', 'Request sent')}
                  </Badge>
                ) : (
                  <Button
                    loading={join.isPending && join.variables === c.slug}
                    onClick={() => join.mutate(c.slug)}
                  >
                    {canJoinDirectly ? tr('Beitreten', 'Join') : tr('Um Aufnahme bitten', 'Ask to join')}
                  </Button>
                )}
              </Group>
            </Paper>
          ))}
        </Stack>

        <Stack gap={4} mt={40}>
          <Text size="sm" c="dimmed">
            {tr('Du gründest einen neuen Verein?', 'Starting a new club?')}{' '}
            <Anchor
              href="/start"
              onClick={(e) => {
                e.preventDefault()
                navigate('/start')
              }}
            >
              {tr('Verein beantragen', 'Request one')}
            </Anchor>
          </Text>
        </Stack>
    </SignedInFrame>
  )
}
