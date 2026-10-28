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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { IconArrowLeft } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import * as authApi from '@/api/auth'

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Waiting for review',
  approved: 'Approved',
  rejected: 'Declined',
}

// Same rules as the backend: lowercase letters, digits and dashes.
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-')
}

/**
 * Start a club: ask the platform for a new one and follow the requests made
 * so far. Once staff approve, the requester owns the club and finds it on
 * the club picker.
 */
export function StartClubScreen() {
  const { authStatus, notify } = useSso()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (authStatus === 'anon')
      navigate(`/login?redirect=${encodeURIComponent(window.location.href)}`, { replace: true })
  }, [authStatus, navigate])

  const authed = authStatus === 'authed'
  const mine = useQuery({
    queryKey: ['club-requests'],
    queryFn: authApi.getMyClubRequests,
    enabled: authed,
  })

  const submit = useMutation({
    mutationFn: authApi.requestClub,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['club-requests'] })
      setName('')
      setSlug('')
      setSlugEdited(false)
      notify('success', 'Request sent', `We will review ${res.request.name} and let you know.`)
    },
    onError: (err: Error) => setError(err.message),
  })

  const send = () => {
    setError('')
    const cleanSlug = slugify(slug)
    if (!name.trim() || !cleanSlug) {
      setError('Give your club a name and an address.')
      return
    }
    if (cleanSlug.length < 3) {
      setError('The address needs at least 3 characters.')
      return
    }
    submit.mutate({ name: name.trim(), slug: cleanSlug })
  }

  if (!authed)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  const requests = mine.data?.requests ?? []

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', padding: '32px 16px' }}>
      <Box style={{ width: '100%', maxWidth: 520, margin: '0 auto' }}>
        <Group gap={10} mb={32} wrap="nowrap">
          <div className="logo-mark" />
          <Text fz={20} className="wordmark">
            hubra
          </Text>
        </Group>

        <Anchor
          size="sm"
          mb="md"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
          onClick={(e) => {
            e.preventDefault()
            navigate('/clubs')
          }}
          href="/clubs"
        >
          <IconArrowLeft size={14} /> Your clubs
        </Anchor>

        <Title order={2} mb={6}>
          Start a club
        </Title>
        <Text size="sm" c="dimmed" mb="lg">
          Tell us what your club is called. We review every new club; once it is approved
          you are its owner and find it under your clubs.
        </Text>

        {error && (
          <Alert color="red" variant="light" mb="md">
            {error}
          </Alert>
        )}

        <Stack gap="md" mb={40}>
          <TextInput
            label="Club name"
            placeholder="Rowing Club Zug"
            value={name}
            onChange={(e) => {
              const value = e.currentTarget.value
              setName(value)
              if (!slugEdited) setSlug(slugify(value))
            }}
          />
          <TextInput
            label="Address"
            description="Used in your club's links. Lowercase letters, digits and dashes."
            placeholder="rowing-zug"
            value={slug}
            onChange={(e) => {
              setSlug(e.currentTarget.value)
              setSlugEdited(true)
            }}
            onKeyDown={(e) => e.key === 'Enter' && send()}
          />
          <Button onClick={send} loading={submit.isPending}>
            Send request
          </Button>
        </Stack>

        <Title order={3} mb="sm">
          Your requests
        </Title>
        {mine.isLoading ? (
          <Loader size="sm" />
        ) : requests.length === 0 ? (
          <Text size="sm" c="dimmed">
            You have not asked for a club yet.
          </Text>
        ) : (
          <Stack gap="sm">
            {requests.map((r) => (
              <Paper key={r.id} withBorder radius="md" p="md">
                <Group justify="space-between" wrap="nowrap" align="flex-start">
                  <Box style={{ minWidth: 0 }}>
                    <Text fw={600} truncate>
                      {r.name}
                    </Text>
                    <Text fz="xs" c="dimmed">
                      {r.slug}
                      {r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString()}` : ''}
                    </Text>
                    {r.admin_note && (
                      <Text fz="xs" mt={4}>
                        {r.admin_note}
                      </Text>
                    )}
                  </Box>
                  <Badge variant="light" color={STATUS_COLORS[r.status] ?? 'gray'} style={{ flexShrink: 0 }}>
                    {STATUS_LABELS[r.status] ?? r.status}
                  </Badge>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Box>
    </div>
  )
}
