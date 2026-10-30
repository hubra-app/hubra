import { useSyncExternalStore } from 'react'
import { Modal, Stack, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { getChangelog } from '@/api/system'
import { qk } from '@/data/keys'
import { setWhatsNewOpen, subscribeWhatsNew, whatsNewOpen } from './whatsNewStore'

/** "Neuigkeiten": the latest changelog entries. */
export function WhatsNewModal() {
  const { t } = useT()
  const opened = useSyncExternalStore(subscribeWhatsNew, whatsNewOpen)
  const { data: changelog } = useQuery({
    queryKey: qk.changelog,
    queryFn: getChangelog,
    enabled: opened,
  })
  const entries = changelog?.entries?.slice(0, 3) ?? []

  return (
    <Modal opened={opened} onClose={() => setWhatsNewOpen(false)} title={t('shell.whatsNew.title')}>
      <Stack gap="md">
        {entries.length > 0 ? (
          entries.map((entry) => (
            <div key={entry.version}>
              <Text fz="sm" fw={700}>
                v{entry.version}
                {entry.date && (
                  <Text component="span" fz="xs" c="dimmed" ml={6}>
                    {entry.date}
                  </Text>
                )}
              </Text>
              {Object.entries(entry.sections).map(([section, items]) =>
                items.length > 0 ? (
                  <div key={section}>
                    <Text fz="xs" fw={600} c="var(--hb-text-2)" mt={6}>
                      {section}
                    </Text>
                    {items.map((item, i) => (
                      <Text key={section + '-' + i} fz="sm" c="var(--hb-text-2)" ml={8}>
                        {item}
                      </Text>
                    ))}
                  </div>
                ) : null,
              )}
            </div>
          ))
        ) : (
          <Text fz="sm" c="dimmed">
            {t('shell.whatsNew.changelogSoon')}
          </Text>
        )}
      </Stack>
    </Modal>
  )
}
