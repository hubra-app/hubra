import { useEffect, useState } from 'react'
import {
  Alert,
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
import { SignedInFrame } from '@/components/SignedInFrame'
import { useLang } from '@/lang'

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
}

const STATUS_LABELS: Record<string, [string, string]> = {
  pending: ['Wird geprüft', 'Waiting for review'],
  approved: ['Freigegeben', 'Approved'],
  rejected: ['Abgelehnt', 'Declined'],
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
  const { tr } = useLang()
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
      notify(
        'success',
        tr('Anfrage gesendet', 'Request sent'),
        tr(
          `Wir prüfen ${res.request.name} und melden uns bei dir.`,
          `We will review ${res.request.name} and let you know.`,
        ),
      )
    },
    onError: (err: Error) => setError(err.message),
  })

  const send = () => {
    setError('')
    const cleanSlug = slugify(slug)
    if (!name.trim() || !cleanSlug) {
      setError(tr('Gib deinem Verein einen Namen und eine Adresse.', 'Give your club a name and an address.'))
      return
    }
    if (cleanSlug.length < 3) {
      setError(tr('Die Adresse braucht mindestens 3 Zeichen.', 'The address needs at least 3 characters.'))
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
    <SignedInFrame
      actions={
        <Button
          variant="subtle"
          size="xs"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => navigate('/clubs')}
        >
          {tr('Meine Vereine', 'My clubs')}
        </Button>
      }
    >
      <Title order={1} fz={30} mb={6}>
        {tr('Verein gründen', 'Start a club')}
      </Title>
      <Text c="dimmed" mb="lg">
        {tr(
          'Sag uns, wie dein Verein heisst. Wir prüfen jeden neuen Verein. Sobald er freigegeben ist, bist du Inhaberin oder Inhaber und findest ihn unter «Meine Vereine».',
          'Tell us what your club is called. We review every new club; once it is approved you are its owner and find it under your clubs.',
        )}
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <Paper withBorder p="lg" mb={40}>
        <Stack gap="md">
          <TextInput
            label={tr('Name des Vereins', 'Club name')}
            placeholder={tr('Ruderclub Zug', 'Rowing Club Zug')}
            size="md"
            value={name}
            onChange={(e) => {
              const value = e.currentTarget.value
              setName(value)
              if (!slugEdited) setSlug(slugify(value))
            }}
          />
          <TextInput
            label={tr('Adresse', 'Address')}
            description={tr(
              'Steht in den Links deines Vereins. Kleinbuchstaben, Ziffern und Bindestriche.',
              "Used in your club's links. Lowercase letters, digits and dashes.",
            )}
            placeholder="ruderclub-zug"
            size="md"
            value={slug}
            onChange={(e) => {
              setSlug(e.currentTarget.value)
              setSlugEdited(true)
            }}
            onKeyDown={(e) => e.key === 'Enter' && send()}
          />
          <Button size="md" onClick={send} loading={submit.isPending}>
            {tr('Anfrage senden', 'Send request')}
          </Button>
        </Stack>
      </Paper>

      <Title order={2} fz={20} mb="sm">
        {tr('Deine Anfragen', 'Your requests')}
      </Title>
      {mine.isLoading ? (
        <Loader size="sm" />
      ) : requests.length === 0 ? (
        <Text size="sm" c="dimmed">
          {tr('Du hast noch keinen Verein beantragt.', 'You have not asked for a club yet.')}
        </Text>
      ) : (
        <Stack gap="sm">
          {requests.map((r) => (
            <Paper key={r.id} withBorder p="md">
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={700} truncate>
                    {r.name}
                  </Text>
                  <Text fz="sm" c="dimmed">
                    {r.slug}
                    {r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString('de-CH')}` : ''}
                  </Text>
                  {r.admin_note && (
                    <Text fz="sm" mt={4}>
                      {r.admin_note}
                    </Text>
                  )}
                </Box>
                <Badge variant="light" color={STATUS_COLORS[r.status] ?? 'gray'} style={{ flexShrink: 0 }}>
                  {STATUS_LABELS[r.status] ? tr(...STATUS_LABELS[r.status]) : r.status}
                </Badge>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
    </SignedInFrame>
  )
}
