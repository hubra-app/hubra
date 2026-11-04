import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Box, Button, Center, Group, Loader, SegmentedControl, Text, Title } from '@mantine/core'
import { Roadmap, ThemeToggle, type RoadmapItem } from '@hubra/ui'
import { useSso } from '@/context/SsoContext'
import { themeLabels, useLang, type Lang } from '@/lang'
import { myRoadmap, publicRoadmap, setVote, type RoadmapResponse } from '@/api/roadmap'

/**
 * /roadmap: the one Hubra roadmap for anyone: what is being built, what comes
 * next, the ideas from the clubs and what shipped. Signed in, people vote.
 */
export function RoadmapScreen() {
  const { tr, lang, setLang } = useLang()
  const { authStatus } = useSso()
  const signedIn = authStatus === 'authed'
  const query = useQuery({
    queryKey: ['roadmap', signedIn],
    queryFn: signedIn ? myRoadmap : publicRoadmap,
    enabled: authStatus !== 'loading',
  })
  const items = query.data?.items ?? []
  const queryClient = useQueryClient()
  const { notify } = useSso()
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
    <div className="graph-bg" style={{ minHeight: '100vh' }}>
      <header className="sso-topbar">
        <Group
          justify="space-between"
          wrap="nowrap"
          style={{ maxWidth: 1160, margin: '0 auto', height: '100%', padding: '0 16px' }}
        >
          <Group gap={10} wrap="nowrap">
            <div className="logo-mark" />
            <Text fz={20} className="wordmark">
              hubra
            </Text>
          </Group>
          <Group gap={4} wrap="nowrap">
            <ThemeToggle labels={themeLabels(tr)} />
            <SegmentedControl
              size="xs"
              radius="md"
              value={lang}
              onChange={(v) => setLang(v as Lang)}
              data={[
                { value: 'de', label: 'DE' },
                { value: 'en', label: 'EN' },
              ]}
              aria-label={tr('Sprache', 'Language')}
            />
          </Group>
        </Group>
      </header>
      <Box style={{ width: '100%', maxWidth: 1160, margin: '0 auto', padding: '32px 16px 64px' }}>
        <Title order={1} fz={30}>
          Roadmap
        </Title>
        <Text c="dimmed" mt={6} maw={680}>
          {tr(
            'Woran wir an Hubra arbeiten und was als Nächstes kommen könnte. Vorschläge kommen aus den Vereinen; deine Stimme hilft beim Entscheiden, was zuerst kommt.',
            'What we are working on in Hubra and what could come next. Ideas come from the clubs; your vote helps decide what comes first.',
          )}
        </Text>
        {!signedIn && authStatus !== 'loading' && (
          <Button
            mt={14}
            variant="light"
            onClick={() =>
              window.location.assign(`/login?redirect=${encodeURIComponent(window.location.href)}`)
            }
          >
            {tr('Anmelden zum Abstimmen', 'Sign in to vote')}
          </Button>
        )}
        {query.isLoading || authStatus === 'loading' ? (
          <Center py={60}>
            <Loader />
          </Center>
        ) : query.isError ? (
          <Text c="red" mt={24}>
            {tr('Die Roadmap konnte nicht geladen werden.', 'The roadmap could not be loaded.')}
          </Text>
        ) : items.length === 0 ? (
          <Text c="dimmed" mt={32}>
            {tr('Noch nichts auf der Roadmap.', 'Nothing on the roadmap yet.')}
          </Text>
        ) : (
          <Box mt={28}>
            <Roadmap
              items={items}
              lang={lang}
              wide
              voting={signedIn ? { onVote: (item) => void onVote(item), pending } : undefined}
            />
          </Box>
        )}
      </Box>
    </div>
  )
}
