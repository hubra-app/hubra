import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowBigUp, IconArrowBigUpFilled } from '@tabler/icons-react'
import { ThemeToggle } from '@hubra/ui'
import { useSso } from '@/context/SsoContext'
import { themeLabels, useLang, type Lang } from '@/lang'
import { myRoadmap, publicRoadmap, setVote, type RoadmapItem, type RoadmapStatus } from '@/api/roadmap'

const COLUMNS: { status: RoadmapStatus; color: string; de: string; en: string }[] = [
  { status: 'in_progress', color: 'orange', de: 'In Arbeit', en: 'In progress' },
  { status: 'planned', color: 'acc', de: 'Geplant', en: 'Planned' },
  { status: 'open', color: 'gray', de: 'Vorgeschlagen', en: 'Suggested' },
  { status: 'done', color: 'green', de: 'Erledigt', en: 'Done' },
]

/**
 * /roadmap: the ideas the Hubra team made public, for anyone. Signed in,
 * people vote; otherwise the vote button leads to sign-in.
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
  const items = query.data ?? []

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
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="lg" mt={28}>
            {COLUMNS.map((col) => {
              const list = items.filter((i) => i.status === col.status)
              return (
                <Stack key={col.status} gap={10}>
                  <Group gap={6}>
                    <Badge variant="light" color={col.color}>
                      {tr(col.de, col.en)}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {list.length}
                    </Text>
                  </Group>
                  {list.length === 0 ? (
                    <Text size="xs" c="dimmed">
                      {tr('Nichts hier.', 'Nothing here.')}
                    </Text>
                  ) : (
                    list.map((item) => <Card key={item.id} item={item} signedIn={signedIn} />)
                  )}
                </Stack>
              )
            })}
          </SimpleGrid>
        )}
      </Box>
    </div>
  )
}

function Card({ item, signedIn }: { item: RoadmapItem; signedIn: boolean }) {
  const { tr } = useLang()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const done = item.status === 'done'

  const toggle = async () => {
    if (!signedIn) {
      window.location.assign(`/login?redirect=${encodeURIComponent(window.location.href)}`)
      return
    }
    setBusy(true)
    try {
      const res = await setVote(item.id, !item.voted)
      queryClient.setQueryData<RoadmapItem[]>(['roadmap', true], (old) =>
        old?.map((i) => (i.id === item.id ? { ...i, votes: res.votes, voted: res.voted } : i)),
      )
    } catch (err) {
      notifications.show({
        color: 'red',
        title: tr('Abstimmen fehlgeschlagen', 'Voting failed'),
        message: (err as Error).message,
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder radius="lg" p="md">
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <UnstyledButton
          onClick={() => void toggle()}
          disabled={busy || done}
          aria-pressed={!!item.voted}
          aria-label={item.voted ? tr('Stimme zurücknehmen', 'Take back your vote') : tr('Dafür stimmen', 'Vote for it')}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            minWidth: 46,
            padding: '6px 4px',
            borderRadius: 10,
            border: '1px solid var(--hb-border)',
            color: item.voted ? 'var(--mantine-color-acc-6)' : 'var(--hb-text-2)',
            background: item.voted ? 'var(--mantine-color-acc-light)' : 'transparent',
            cursor: done ? 'default' : 'pointer',
          }}
        >
          {item.voted ? <IconArrowBigUpFilled size={18} /> : <IconArrowBigUp size={18} />}
          <Text size="sm" fw={700}>
            {item.votes}
          </Text>
        </UnstyledButton>
        <div style={{ minWidth: 0 }}>
          <Text fw={600} size="sm" style={{ wordBreak: 'break-word' }}>
            {item.title}
          </Text>
          <Text size="xs" c="dimmed" lineClamp={5} style={{ whiteSpace: 'pre-wrap' }}>
            {item.description}
          </Text>
        </div>
      </Group>
    </Paper>
  )
}
