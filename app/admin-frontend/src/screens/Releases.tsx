import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Center, Loader, Text } from '@mantine/core'
import { ReleaseNotes, Roadmap } from '@hubra/ui'
import { PageHead, Tabs } from '@/components/ui'
import { getChangelog, getRoadmap } from '@/api/platform'
import { useLang } from '@/lang'

const TABS = ['changelog', 'roadmap'] as const
type Tab = (typeof TABS)[number]

/** Changelog (every release, newest first) and roadmap, for everyone in manage. */
export function Releases() {
  const { tr, lang } = useLang()
  const location = useLocation()
  const navigate = useNavigate()
  const last = location.pathname.split('/').pop() as Tab
  const tab: Tab = TABS.includes(last) ? last : 'changelog'

  const changelog = useQuery({
    queryKey: ['changelog', lang],
    queryFn: () => getChangelog(lang),
    enabled: tab === 'changelog',
  })
  const roadmap = useQuery({ queryKey: ['roadmap'], queryFn: getRoadmap, enabled: tab === 'roadmap' })
  const query = tab === 'changelog' ? changelog : roadmap

  return (
    <div>
      <PageHead
        title={tr('Neuigkeiten', "What's new")}
        desc={
          tab === 'changelog'
            ? tr('Was sich in Hubra geändert hat, neueste Version zuerst.', 'What changed in Hubra, newest version first.')
            : tr(
                'Woran wir arbeiten und was als Nächstes kommt.',
                'What we are working on and what comes next.',
              )
        }
      />
      <Tabs
        tabs={[
          { id: 'changelog', label: tr('Änderungen', 'Changelog') },
          { id: 'roadmap', label: 'Roadmap' },
        ]}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/whats-new/${id}`)}
      />
      <div style={{ maxWidth: tab === 'changelog' ? 860 : undefined }}>
        {query.isLoading ? (
          <Center py="xl">
            <Loader size="sm" />
          </Center>
        ) : query.isError ? (
          <Text c="red" fz="sm">
            {query.error instanceof Error ? query.error.message : tr('Unbekannter Fehler', 'Unknown error')}
          </Text>
        ) : tab === 'changelog' ? (
          <ReleaseNotes entries={changelog.data?.entries ?? []} lang={lang} pageSize={10} />
        ) : (
          <Roadmap items={roadmap.data?.items ?? []} lang={lang} wide />
        )}
      </div>
    </div>
  )
}
