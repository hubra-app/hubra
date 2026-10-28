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
import { IconArrowRight, IconLogout, IconSearch } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { clearTokens } from '@hubra/api-client'
import { useSso } from '@/context/SsoContext'
import { clubAppUrl } from '@/redirect'
import * as authApi from '@/api/auth'

/**
 * The club picker: where everyone lands after signing in. Lists their clubs
 * (and the manager portal for platform managers), and lets them find another
 * club and ask to join it (platform managers join straight away).
 */
export function ClubsScreen() {
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
        notify('success', `You joined ${res.club.name}`)
      } else {
        notify(
          'success',
          'Request sent',
          `${res.club.name} will review it. You can open the club once they accept.`,
        )
      }
    },
    onError: (err: Error) => notify('error', 'Could not join', err.message),
  })

  const openClub = async (slug: string) => {
    setOpening(slug)
    try {
      await authApi.switchTenant(slug)
      window.location.assign(clubAppUrl(urls, slug))
    } catch (err: unknown) {
      setOpening(null)
      notify('error', 'Could not open the club', err instanceof Error ? err.message : undefined)
    }
  }

  const signOut = async () => {
    await authApi.logout()
    clearTokens()
    window.location.assign('/login')
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
    <div className="graph-bg" style={{ minHeight: '100vh', padding: '32px 16px' }}>
      <Box style={{ width: '100%', maxWidth: 520, margin: '0 auto' }}>
        <Group justify="space-between" mb={32} wrap="nowrap">
          <Group gap={10} wrap="nowrap">
            <div className="logo-mark" />
            <Text fz={20} className="wordmark">
              hubra
            </Text>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconLogout size={16} />}
            onClick={signOut}
          >
            Sign out
          </Button>
        </Group>

        {(isManager || runsAClub) && (
          <Paper withBorder radius="md" p="md" mb="xl">
            <Group justify="space-between" wrap="nowrap">
              <Box style={{ minWidth: 0 }}>
                <Text fw={600}>Manager portal</Text>
                <Text fz="xs" c="dimmed">
                  {isManager
                    ? 'Clubs, requests, roles and plugins of this platform'
                    : 'Admins and settings of the clubs you run'}
                </Text>
              </Box>
              <Button
                component="a"
                href={urls.manage}
                variant="light"
                style={{ flexShrink: 0 }}
                rightSection={<IconArrowRight size={16} />}
              >
                Open
              </Button>
            </Group>
          </Paper>
        )}

        <Title order={2} mb={6}>
          Your clubs
        </Title>
        {mine.isLoading ? (
          <Loader size="sm" my="md" />
        ) : myClubs.length === 0 ? (
          <Text size="sm" c="dimmed" mb="xl">
            You are not a member of a club yet. Find yours below and ask to join.
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
                          {t.admin_level === 'owner' ? 'Owner' : 'Admin'}
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
                    Open
                  </Button>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}

        <Title order={3} mb={6}>
          Find a club
        </Title>
        <TextInput
          placeholder="Club name"
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          mb="md"
          aria-label="Search clubs"
        />

        {found.isFetching && <Loader size="sm" />}
        {found.isError && (
          <Alert color="red" variant="light">
            {(found.error as Error).message}
          </Alert>
        )}
        {!found.isFetching && debounced.length >= 2 && results.length === 0 && (
          <Text size="sm" c="dimmed">
            No club matches “{debounced}”.
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
                    Open
                  </Button>
                ) : c.membership === 'pending' ? (
                  <Badge variant="light" color="gray">
                    Request sent
                  </Badge>
                ) : (
                  <Button
                    loading={join.isPending && join.variables === c.slug}
                    onClick={() => join.mutate(c.slug)}
                  >
                    {canJoinDirectly ? 'Join' : 'Ask to join'}
                  </Button>
                )}
              </Group>
            </Paper>
          ))}
        </Stack>

        <Stack gap={4} mt={40}>
          <Text size="sm" c="dimmed">
            Starting a new club?{' '}
            <Anchor
              href="/start"
              onClick={(e) => {
                e.preventDefault()
                navigate('/start')
              }}
            >
              Request one
            </Anchor>
          </Text>
        </Stack>
      </Box>
    </div>
  )
}
