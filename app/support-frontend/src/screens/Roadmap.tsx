import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Button, Center, Group, Loader, Text } from '@mantine/core'
import { IconBulb } from '@tabler/icons-react'
import { Roadmap, type RoadmapItem } from '@hubra/ui'
import { Page } from '@/components/Layout'
import { useAuth } from '@/auth'
import { useLang } from '@/lang'
import { myRoadmap, publicRoadmap, setVote, type RoadmapResponse } from '@/api/support'

/**
 * /roadmap: the one Hubra roadmap for anyone: what is being built, what comes
 * next, the ideas from the clubs and what shipped. Signed in, people vote
 * (one vote per person and item; reading needs no account).
 */
export function RoadmapScreen() {
  const { tr, lang } = useLang()
  const { status, notify, signInUrl } = useAuth()
  const signedIn = status === 'authed'
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['roadmap', signedIn],
    queryFn: signedIn ? myRoadmap : publicRoadmap,
    enabled: status !== 'loading',
  })
  const items = query.data?.items ?? []
  const [pending, setPending] = useState<string | null>(null)

  const onVote = async (item: RoadmapItem) => {
    setPending(item.id)
    try {
      const res = await setVote(item, !item.voted)
      queryClient.setQueryData<RoadmapResponse>(['roadmap', true], (old) =>
        old
          ? { ...old, items: old.items.map((i) => (i.id === item.id ? { ...i, votes: res.votes, voted: res.voted } : i)) }
          : old,
      )
    } catch (err) {
      notify('error', tr('Abstimmen fehlgeschlagen', 'Voting failed'), (err as Error).message)
    } finally {
      setPending(null)
    }
  }

  return (
    <Page
      title="Roadmap"
      intro={tr(
        'Woran wir an Hubra arbeiten und was als Nächstes kommen könnte. Vorschläge kommen aus den Vereinen; deine Stimme hilft beim Entscheiden, was zuerst kommt.',
        'What we are working on in Hubra and what could come next. Ideas come from the clubs; your vote helps decide what comes first.',
      )}
      actions={
        <Button component={Link} to="/idee" variant="light" leftSection={<IconBulb size={16} />}>
          {tr('Idee vorschlagen', 'Suggest an idea')}
        </Button>
      }
    >
      {status === 'anon' && (
        <Group mb={20} gap="sm">
          <Button component="a" href={signInUrl()} variant="filled">
            {tr('Anmelden zum Abstimmen', 'Sign in to vote')}
          </Button>
          <Text size="sm" c="dimmed">
            {tr('Lesen geht ohne Konto, abstimmen mit deinem Hubra-Konto.', 'Reading needs no account; voting uses your Hubra account.')}
          </Text>
        </Group>
      )}
      {query.isLoading || status === 'loading' ? (
        <Center py={60}>
          <Loader />
        </Center>
      ) : query.isError ? (
        <Text c="red">{tr('Die Roadmap konnte nicht geladen werden.', 'The roadmap could not be loaded.')}</Text>
      ) : items.length === 0 ? (
        <Text c="dimmed">{tr('Noch nichts auf der Roadmap.', 'Nothing on the roadmap yet.')}</Text>
      ) : (
        <Box>
          <Roadmap
            items={items}
            lang={lang}
            wide
            voting={signedIn ? { onVote: (item) => void onVote(item), pending } : undefined}
          />
        </Box>
      )}
    </Page>
  )
}
