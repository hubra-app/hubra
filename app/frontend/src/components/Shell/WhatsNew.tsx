import { useEffect, useState, useSyncExternalStore } from 'react'
import { Center, Loader, Modal, SegmentedControl, Stack, Text } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { ReleaseNotes, Roadmap, latestReleaseKey } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { useRoadmap } from '@/screens/private/support/roadmapData'
import { markWhatsNewSeen, setWhatsNewOpen, subscribeWhatsNew, whatsNewOpen } from './whatsNewStore'
import { useChangelog, useReleaseLang } from './whatsNewData'

type View = 'news' | 'roadmap'

/**
 * "Neuigkeiten": the newest release open at the top, older versions one at a
 * time below it, and the roadmap on a second tab. Full screen on phones.
 */
export function WhatsNewModal() {
  const { t } = useT()
  const lang = useReleaseLang()
  const phone = useMediaQuery('(max-width: 47.99em)')
  const opened = useSyncExternalStore(subscribeWhatsNew, whatsNewOpen)
  const [view, setView] = useState<View>('news')
  const changelog = useChangelog(opened)
  const roadmap = useRoadmap(opened && view === 'roadmap')

  useEffect(() => {
    if (opened && changelog.data) markWhatsNewSeen(latestReleaseKey(changelog.data.entries))
  }, [opened, changelog.data])

  const loading = view === 'news' ? changelog.isLoading : roadmap.isLoading
  const failed = view === 'news' ? changelog.isError : roadmap.isError

  return (
    <Modal
      opened={opened}
      onClose={() => setWhatsNewOpen(false)}
      title={t('shell.whatsNew.title')}
      size="lg"
      fullScreen={phone}
      radius={phone ? 0 : undefined}
    >
      <Stack gap="md">
        <SegmentedControl
          fullWidth
          value={view}
          onChange={(v) => setView(v as View)}
          data={[
            { value: 'news', label: t('shell.whatsNew.tabNews', 'Was ist neu') },
            { value: 'roadmap', label: t('shell.whatsNew.tabRoadmap', 'Roadmap') },
          ]}
        />
        {loading ? (
          <Center py="xl">
            <Loader size="sm" />
          </Center>
        ) : failed ? (
          <Text fz="sm" c="dimmed">
            {t('shell.whatsNew.changelogSoon')}
          </Text>
        ) : view === 'news' ? (
          <ReleaseNotes entries={changelog.data?.entries ?? []} lang={lang} />
        ) : (
          <Roadmap items={roadmap.items} lang={lang} voting={roadmap.voting} />
        )}
      </Stack>
    </Modal>
  )
}
