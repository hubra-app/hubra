import { Center, Loader, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { ReleaseNotes } from '@hubra/ui'
import { Page } from '@/components/Layout'
import { useLang } from '@/lang'
import { changelog } from '@/api/support'

/** /neuigkeiten: the release notes (CHANGELOG.md / CHANGELOG.de.md). */
export function WhatsNewScreen() {
  const { tr, lang } = useLang()
  const query = useQuery({ queryKey: ['changelog', lang], queryFn: () => changelog(lang) })
  return (
    <Page
      narrow
      title={tr('Neuigkeiten', "What's new")}
      intro={tr(
        'Was sich in Hubra geändert hat, neueste Version zuerst. Was noch kommt, steht auf der Roadmap.',
        'What changed in Hubra, newest version first. What is still to come is on the roadmap.',
      )}
    >
      {query.isLoading ? (
        <Center py={60}>
          <Loader />
        </Center>
      ) : query.isError ? (
        <Text c="red">{tr('Die Neuigkeiten konnten nicht geladen werden.', 'The release notes could not be loaded.')}</Text>
      ) : (
        <ReleaseNotes entries={query.data?.entries ?? []} lang={lang} />
      )}
    </Page>
  )
}
