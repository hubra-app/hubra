import { useQuery } from '@tanstack/react-query'
import { Center, Loader, Text } from '@mantine/core'
import { ReleaseNotes, Roadmap } from '@hubra/ui'
import { getChangelog, getRoadmap } from '@/api/platform'
import { useLang } from '@/lang'

function Loading({ query }: { query: { isLoading: boolean; isError: boolean; error: unknown } }) {
  const { tr } = useLang()
  if (query.isLoading)
    return (
      <Center py="xl">
        <Loader size="sm" />
      </Center>
    )
  return (
    <Text c="red" fz="sm">
      {query.error instanceof Error ? query.error.message : tr('Unbekannter Fehler', 'Unknown error')}
    </Text>
  )
}

/** Every release, newest first. */
export function ChangelogPanel() {
  const { lang } = useLang()
  const query = useQuery({ queryKey: ['changelog', lang], queryFn: () => getChangelog(lang) })
  return (
    <div style={{ maxWidth: 860 }}>
      {query.isLoading || query.isError ? (
        <Loading query={query} />
      ) : (
        <ReleaseNotes entries={query.data?.entries ?? []} lang={lang} pageSize={10} />
      )}
    </div>
  )
}

/** What we are working on and what comes next. */
export function RoadmapPanel() {
  const { lang } = useLang()
  const query = useQuery({ queryKey: ['roadmap'], queryFn: getRoadmap })
  return query.isLoading || query.isError ? (
    <Loading query={query} />
  ) : (
    <Roadmap items={query.data?.items ?? []} lang={lang} wide />
  )
}
