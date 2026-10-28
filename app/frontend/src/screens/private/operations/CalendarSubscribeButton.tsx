import { useState } from 'react'
import { Button, CopyButton, Group, Modal, Text, TextInput } from '@mantine/core'
import { IconCalendarShare } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { getCalendarFeedUrl } from '@/api/events'

/** Shows the member's personal calendar feed URL to add in a calendar app. */
export function CalendarSubscribeButton() {
  const { t } = useT()
  const { notify } = useToast()
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const open = async () => {
    setLoading(true)
    try {
      setUrl(await getCalendarFeedUrl())
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Button variant="default" onClick={open} loading={loading}>
        <IconCalendarShare size={16} />
        {t('events.subscribe.button', 'Add to my calendar')}
      </Button>
      <Modal
        opened={url !== null}
        onClose={() => setUrl(null)}
        title={t('events.subscribe.title', 'Subscribe to club events')}
        centered
      >
        <Text fz="sm" mb="sm">
          {t(
            'events.subscribe.hint',
            'Add this address as a calendar subscription (Google Calendar: "From URL", Apple Calendar: "New Calendar Subscription"). New and changed events show up there on their own. The link is personal; do not share it.',
          )}
        </Text>
        <Group gap="xs" wrap="nowrap">
          <TextInput
            value={url ?? ''}
            readOnly
            style={{ flex: 1 }}
            onFocus={(e) => e.currentTarget.select()}
          />
          <CopyButton value={url ?? ''}>
            {({ copied, copy }) => (
              <Button onClick={copy} variant={copied ? 'light' : 'filled'}>
                {copied
                  ? t('events.subscribe.copied', 'Copied')
                  : t('events.subscribe.copy', 'Copy')}
              </Button>
            )}
          </CopyButton>
        </Group>
      </Modal>
    </>
  )
}
